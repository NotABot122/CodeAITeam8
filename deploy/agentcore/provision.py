"""Create, update, and delete the AWS resources behind the protected runtime.

`deploy()` is idempotent: it finds each resource by name and creates only what is missing,
then uploads a fresh package and updates the runtime. Resources:

  Amazon Cognito user pool   the OAuth 2.0 authorization server (machine-to-machine:
                             client_credentials grant, one scope)
  IAM role                   execution role the runtime assumes (logs + reading its package)
  S3 bucket                  holds the deployment package
  AgentCore Runtime          `customJWTAuthorizer` (AgentCore Identity inbound auth) that accepts
                             only access tokens from this pool, for this client, with this scope
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from . import package
from .settings import (CLIENT_NAME, REGION, RESOURCE_SERVER_ID, ROLE_NAME, RUNTIME_NAME, RUNTIME_PYTHON, SCOPE,
                       STATE_FILE, USER_POOL_NAME, State, bucket_name, cognito_domain)

POLL_SECONDS = 10
READY, FAILED = "READY", ("CREATE_FAILED", "UPDATE_FAILED")


def _client(service: str):
    return boto3.client(service, region_name=REGION)


def _say(message: str) -> None:
    print(f"  {message}", flush=True)


# Amazon Cognito ---------------------------------------------------------------------------

def _ensure_user_pool(cognito) -> str:
    for page in cognito.get_paginator("list_user_pools").paginate(MaxResults=60):
        for pool in page["UserPools"]:
            if pool["Name"] == USER_POOL_NAME:
                return pool["Id"]
    _say(f"creating user pool {USER_POOL_NAME}")
    return cognito.create_user_pool(PoolName=USER_POOL_NAME)["UserPool"]["Id"]


def _ensure_resource_server(cognito, pool_id: str) -> None:
    try:
        cognito.describe_resource_server(UserPoolId=pool_id, Identifier=RESOURCE_SERVER_ID)
    except cognito.exceptions.ResourceNotFoundException:
        _say(f"creating resource server {RESOURCE_SERVER_ID} with scope {SCOPE}")
        cognito.create_resource_server(
            UserPoolId=pool_id, Identifier=RESOURCE_SERVER_ID, Name="CodeAI readiness diagnostic",
            Scopes=[{"ScopeName": SCOPE.split("/", 1)[1], "ScopeDescription": "Call the diagnostic runtime"}])


def _ensure_domain(cognito, pool_id: str, domain: str) -> None:
    current = cognito.describe_user_pool_domain(Domain=domain)["DomainDescription"]
    if current.get("UserPoolId") == pool_id:
        return
    if current:
        raise RuntimeError(f"Cognito domain {domain!r} belongs to another user pool")
    _say(f"creating hosted domain {domain}")
    cognito.create_user_pool_domain(Domain=domain, UserPoolId=pool_id)


def _ensure_client(cognito, pool_id: str) -> str:
    for page in cognito.get_paginator("list_user_pool_clients").paginate(UserPoolId=pool_id, MaxResults=60):
        for client in page["UserPoolClients"]:
            if client["ClientName"] == CLIENT_NAME:
                return client["ClientId"]
    _say(f"creating app client {CLIENT_NAME} (client_credentials)")
    return cognito.create_user_pool_client(
        UserPoolId=pool_id, ClientName=CLIENT_NAME, GenerateSecret=True,
        AllowedOAuthFlowsUserPoolClient=True, AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=[SCOPE], AccessTokenValidity=60, TokenValidityUnits={"AccessToken": "minutes"},
    )["UserPoolClient"]["ClientId"]


def client_secret(state: State) -> str:
    """Read the client secret from Cognito when it is needed; it is never written to disk."""
    client = _client("cognito-idp").describe_user_pool_client(UserPoolId=state.user_pool_id, ClientId=state.client_id)
    return client["UserPoolClient"]["ClientSecret"]


# IAM and S3 -------------------------------------------------------------------------------

def _ensure_role(iam, state: State) -> str:
    trust = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {  # confused-deputy protection
                "StringEquals": {"aws:SourceAccount": state.account_id},
                "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{REGION}:{state.account_id}:*"},
            },
        }],
    }
    log_group = f"arn:aws:logs:{REGION}:{state.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
    permissions = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": ["logs:CreateLogGroup", "logs:DescribeLogStreams"], "Resource": log_group},
            {"Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
             "Resource": f"{log_group}:log-stream:*"},
            {"Effect": "Allow", "Action": "logs:DescribeLogGroups",
             "Resource": f"arn:aws:logs:{REGION}:{state.account_id}:log-group:*"},
            {"Effect": "Allow", "Action": "s3:GetObject",
             "Resource": f"arn:aws:s3:::{state.bucket}/{RUNTIME_NAME}/*"},
        ],
    }
    try:
        role_arn = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
        iam.update_assume_role_policy(RoleName=ROLE_NAME, PolicyDocument=json.dumps(trust))
    except iam.exceptions.NoSuchEntityException:
        _say(f"creating execution role {ROLE_NAME}")
        role_arn = iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(trust),
                                   Description="AgentCore Runtime execution role for the CodeAI diagnostic")["Role"]["Arn"]
    iam.put_role_policy(RoleName=ROLE_NAME, PolicyName="runtime", PolicyDocument=json.dumps(permissions))
    return role_arn


def _ensure_bucket(s3, state: State) -> None:
    try:
        s3.head_bucket(Bucket=state.bucket, ExpectedBucketOwner=state.account_id)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
            raise
        _say(f"creating bucket {state.bucket}")
        location = {} if REGION == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": REGION}}
        s3.create_bucket(Bucket=state.bucket, ObjectOwnership="BucketOwnerEnforced", **location)
        s3.put_public_access_block(Bucket=state.bucket, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    # The package holds only code (no student data). Encrypted at rest by default (SSE-S3); TLS-only on the wire.
    s3.put_bucket_policy(Bucket=state.bucket, ExpectedBucketOwner=state.account_id, Policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
                       "Resource": [f"arn:aws:s3:::{state.bucket}", f"arn:aws:s3:::{state.bucket}/*"],
                       "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}))


# AgentCore Runtime ------------------------------------------------------------------------

def _runtime_config(state: State) -> Dict[str, Any]:
    return {
        "agentRuntimeArtifact": {"codeConfiguration": {
            "code": {"s3": {"bucket": state.bucket, "prefix": state.code_key}},
            "runtime": RUNTIME_PYTHON,
            "entryPoint": ["main.py"],
        }},
        "roleArn": state.role_arn,
        # PUBLIC suits this isolated workshop account; use VPC mode for production.
        "networkConfiguration": {"networkMode": "PUBLIC"},
        "protocolConfiguration": {"serverProtocol": "HTTP"},
        # Inbound auth through AgentCore Identity: only Cognito access tokens issued to our
        # client with our scope get through. Without this block the runtime uses IAM SigV4.
        "authorizerConfiguration": {"customJWTAuthorizer": {
            "discoveryUrl": state.discovery_url,
            "allowedClients": [state.client_id],
            "allowedScopes": [SCOPE],
        }},
        "lifecycleConfiguration": {"idleRuntimeSessionTimeout": 300, "maxLifetime": 1800},
        "environmentVariables": {"CODEAI_AI": "off"},   # keyword rules; no model calls, no Bedrock permissions
    }


def _find_runtime(control) -> Optional[Dict[str, Any]]:
    for page in control.get_paginator("list_agent_runtimes").paginate():
        for runtime in page["agentRuntimes"]:
            if runtime["agentRuntimeName"] == RUNTIME_NAME:
                return runtime
    return None


def _retry_while_role_propagates(call: Callable[[], Dict[str, Any]], attempts: int = 12) -> Dict[str, Any]:
    """A new IAM role can take a few seconds before AgentCore is allowed to assume it."""
    for attempt in range(attempts):
        try:
            return call()
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ValidationException" or "role" not in str(exc).lower() \
                    or attempt == attempts - 1:
                raise
            time.sleep(POLL_SECONDS)
    raise AssertionError("unreachable")


def _wait_until_ready(control, runtime_id: str) -> Dict[str, Any]:
    while True:
        runtime = control.get_agent_runtime(agentRuntimeId=runtime_id)
        if runtime["status"] == READY:
            return runtime
        if runtime["status"] in FAILED:
            raise RuntimeError(f"runtime {runtime['status']}: {runtime.get('failureReason', 'no reason given')}")
        _say(f"runtime status {runtime['status']} ...")
        time.sleep(POLL_SECONDS)


def _deploy_runtime(control, state: State) -> Dict[str, Any]:
    config = _runtime_config(state)
    existing = _find_runtime(control)
    if existing:
        _say(f"updating runtime {RUNTIME_NAME}")
        _retry_while_role_propagates(lambda: control.update_agent_runtime(
            agentRuntimeId=existing["agentRuntimeId"], **config))
        runtime_id = existing["agentRuntimeId"]
    else:
        _say(f"creating runtime {RUNTIME_NAME}")
        runtime_id = _retry_while_role_propagates(lambda: control.create_agent_runtime(
            agentRuntimeName=RUNTIME_NAME, description="CodeAI readiness diagnostic, JWT-protected", **config,
        ))["agentRuntimeId"]
    return _wait_until_ready(control, runtime_id)


# Commands ---------------------------------------------------------------------------------

def deploy() -> State:
    account_id = _client("sts").get_caller_identity()["Account"]
    state = State.load() or State()
    state.region, state.account_id = REGION, account_id
    state.bucket = bucket_name(account_id)
    state.code_key = f"{RUNTIME_NAME}/deployment_package.zip"
    state.domain = cognito_domain(account_id)

    print("Identity provider (Amazon Cognito)")
    cognito = _client("cognito-idp")
    state.user_pool_id = _ensure_user_pool(cognito)
    _ensure_resource_server(cognito, state.user_pool_id)
    _ensure_domain(cognito, state.user_pool_id, state.domain)
    state.client_id = _ensure_client(cognito, state.user_pool_id)
    state.save()

    print("Execution role and code bucket")
    s3 = _client("s3")
    _ensure_bucket(s3, state)
    state.role_arn = _ensure_role(_client("iam"), state)
    state.save()

    print("Deployment package")
    zip_path = package.build()
    _say(f"built {zip_path.name} ({zip_path.stat().st_size // 1024} KiB), uploading")
    s3.upload_file(str(zip_path), state.bucket, state.code_key, ExtraArgs={"ExpectedBucketOwner": account_id})

    print("AgentCore Runtime")
    runtime = _deploy_runtime(_client("bedrock-agentcore-control"), state)
    state.runtime_id, state.runtime_arn = runtime["agentRuntimeId"], runtime["agentRuntimeArn"]
    state.save()
    _say(f"READY: {state.runtime_arn} (version {runtime['agentRuntimeVersion']})")
    return state


def destroy() -> None:
    """Delete everything `deploy` created. The state file is removed last."""
    state = State.load()
    if state is None:
        print("Nothing to delete: no state file.")
        return
    control = _client("bedrock-agentcore-control")
    if state.runtime_id:
        _say(f"deleting runtime {state.runtime_id}")
        try:
            control.delete_agent_runtime(agentRuntimeId=state.runtime_id)
            while _find_runtime(control):
                time.sleep(POLL_SECONDS)
        except control.exceptions.ResourceNotFoundException:
            pass
    cognito = _client("cognito-idp")
    if state.user_pool_id:
        _say(f"deleting user pool {state.user_pool_id} and domain {state.domain}")
        try:
            cognito.delete_user_pool_domain(Domain=state.domain, UserPoolId=state.user_pool_id)
        except ClientError:
            pass  # domain already gone
        try:
            cognito.delete_user_pool(UserPoolId=state.user_pool_id)
        except cognito.exceptions.ResourceNotFoundException:
            pass
    iam = _client("iam")
    try:
        iam.delete_role_policy(RoleName=ROLE_NAME, PolicyName="runtime")
        iam.delete_role(RoleName=ROLE_NAME)
        _say(f"deleted role {ROLE_NAME}")
    except iam.exceptions.NoSuchEntityException:
        pass
    if state.bucket:
        bucket = boto3.resource("s3", region_name=REGION).Bucket(state.bucket)
        try:
            bucket.objects.all().delete()
            bucket.delete()
            _say(f"deleted bucket {state.bucket}")
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchBucket":
                raise
    (package.BUILD_DIR / "deployment_package.zip").unlink(missing_ok=True)
    STATE_FILE.unlink(missing_ok=True)
