"""Show that the runtime's inbound auth works: calls without a valid token are rejected.

Four calls to the deployed runtime, each with an expected result:

  1. no Authorization header           -> 401 from AgentCore, with a WWW-Authenticate header
  2. a forged bearer token             -> 401/403 from AgentCore (right claims, fake signature)
  3. AWS SigV4 (boto3, admin creds)    -> rejected: a JWT runtime does not accept IAM auth
  4. a Cognito access token            -> 200 with the validate_submission output

The container never sees calls 1-3. Tokens are never printed.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from . import provision
from .settings import SCOPE, State

SAMPLE_INPUT = {
    "lesson_id": "weather-station-readiness",
    "task_id": "repeat-explain",
    "attempt_no": 1,
    "submission_text": "you add the rain for each day again and again until the days run out",
    "rubric_id": "WS-DIAG-v0.1-draft",
}


@dataclass
class Response:
    status: int
    body: str
    www_authenticate: Optional[str] = None


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def invoke_url(state: State) -> str:
    arn = urllib.parse.quote(state.runtime_arn, safe="")
    return f"https://bedrock-agentcore.{state.region}.amazonaws.com/runtimes/{arn}/invocations?qualifier=DEFAULT"


def _post(url: str, body: bytes, headers: Dict[str, str]) -> Response:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as reply:
            return Response(reply.status, reply.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return Response(error.code, error.read().decode("utf-8", "replace"), error.headers.get("WWW-Authenticate"))


def access_token(state: State) -> str:
    """OAuth 2.0 client_credentials grant against the Cognito token endpoint."""
    basic = base64.b64encode(f"{state.client_id}:{provision.client_secret(state)}".encode()).decode()
    reply = _post(state.token_url, urllib.parse.urlencode({"grant_type": "client_credentials", "scope": SCOPE}).encode(),
                  {"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"})
    if reply.status != 200:
        raise RuntimeError(f"token endpoint returned {reply.status}: {reply.body[:200]}")
    return json.loads(reply.body)["access_token"]


def call_runtime(state: State, token: Optional[str], payload: Dict = SAMPLE_INPUT) -> Response:
    headers = {"Content-Type": "application/json",
               "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": str(uuid.uuid4())}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return _post(invoke_url(state), json.dumps(payload).encode(), headers)


def _rejected(name: str, reply: Response, allowed: tuple) -> Check:
    detail = f"HTTP {reply.status} {reply.body[:160].strip()}"
    if reply.www_authenticate:
        detail += f"\n      WWW-Authenticate: {reply.www_authenticate}"
    return Check(name, reply.status in allowed, detail)


def _no_token(state: State) -> Check:
    return _rejected("no token", call_runtime(state, None), (401,))


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _forged_token(state: State) -> Check:
    """Every claim the authorizer checks is right; only the signature is fake."""
    issuer = state.discovery_url.rsplit("/.well-known/", 1)[0]
    claims = {"iss": issuer, "client_id": state.client_id, "scope": SCOPE, "token_use": "access",
              "iat": int(time.time()), "exp": int(time.time()) + 3600}
    forged = ".".join([_b64url(b'{"alg":"RS256","typ":"JWT"}'), _b64url(json.dumps(claims).encode()),
                       _b64url(b"not-a-signature")])
    return _rejected("forged token (right claims, fake signature)", call_runtime(state, forged), (401, 403))


def _sigv4(state: State) -> Check:
    client = boto3.client("bedrock-agentcore", region_name=state.region)
    try:
        client.invoke_agent_runtime(agentRuntimeArn=state.runtime_arn, qualifier="DEFAULT",
                                    runtimeSessionId=str(uuid.uuid4()), payload=json.dumps(SAMPLE_INPUT).encode())
    except ClientError as exc:
        error = exc.response["Error"]
        return Check("IAM SigV4 instead of a token", True, f"{error['Code']}: {error.get('Message', '')[:160]}")
    return Check("IAM SigV4 instead of a token", False, "accepted, but the runtime should only take JWTs")


def _valid_token(state: State) -> Check:
    reply = call_runtime(state, access_token(state))
    ok = reply.status == 200 and json.loads(reply.body).get("contract_version") == "0.2"
    return Check("valid Cognito access token", ok, f"HTTP {reply.status} {reply.body[:240]}")


CHECKS: List[Callable[[State], Check]] = [_no_token, _forged_token, _sigv4, _valid_token]


def run(state: State) -> bool:
    print(f"Runtime: {state.runtime_arn}\nAuthorizer: {state.discovery_url}\n")
    results = []
    for number, check in enumerate(CHECKS, 1):
        result = check(state)
        results.append(result.passed)
        print(f"{number}. {result.name}: {'as expected' if result.passed else 'UNEXPECTED'}\n      {result.detail}\n")
    return all(results)
