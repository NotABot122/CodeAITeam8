# Readiness diagnostic on AgentCore Runtime, behind inbound OAuth

This folder deploys the readiness diagnostic's `validate_submission` tool (contract v0.2, keyword rules, no model calls)
to Amazon Bedrock AgentCore Runtime. The runtime only accepts OAuth 2.0 access tokens. AgentCore Identity checks each
token before the request reaches the code, so a call without a valid token never runs.

```bash
pip install --user boto3                  # plus AWS credentials for the target account
python3 -m deploy.agentcore deploy        # create or update everything (idempotent, about 1 minute)
python3 -m deploy.agentcore demo          # 4 calls; exits 1 if any result is not the expected one
python3 -m deploy.agentcore destroy       # delete everything deploy created
```

The region is `us-west-2` (change it with `CODEAI_AWS_REGION`).

## How it fits together

```
caller ──(1) client_credentials──▶ Amazon Cognito token endpoint ──▶ access token (scope codeai-diagnostic/invoke)
caller ──(2) POST /invocations, Authorization: Bearer <token>──▶ AgentCore Runtime
                                    │  customJWTAuthorizer (AgentCore Identity):
                                    │  signature and expiry against the pool's JWKS, client_id, scope
                                    ▼
                            main.py (app.py) ──▶ diagnostic.tool_server.validate_submission_tool
```

| Resource | Name | Why |
|---|---|---|
| Cognito user pool, resource server, hosted domain | `codeai-team8-agentcore`, `codeai-diagnostic`, `codeai-team8-<account>` | The OAuth authorization server. The machine-to-machine client uses the `client_credentials` grant and gets one scope. |
| Cognito app client | `codeai-team8-diagnostic-caller` | The caller. Its secret stays in Cognito; `demo` reads it when it needs a token and never writes it to disk. |
| IAM role | `CodeAITeam8DiagnosticRuntime` | The execution role. It can write its own logs and read its package, nothing else. The trust policy is limited to this account's AgentCore resources (`aws:SourceAccount`, `aws:SourceArn`). |
| S3 bucket | `codeai-team8-agentcore-code-<account>-<region>` | Holds the direct-code deployment zip (code only, no student data). Public access is blocked, ACLs are off, and a bucket policy refuses non-TLS requests. |
| AgentCore Runtime | `codeai_team8_diagnostic` | HTTP protocol, Python 3.12. The authorizer is the part that matters: |

```python
"authorizerConfiguration": {"customJWTAuthorizer": {
    "discoveryUrl": "https://cognito-idp.<region>.amazonaws.com/<pool-id>/.well-known/openid-configuration",
    "allowedClients": ["<client-id>"],
    "allowedScopes": ["codeai-diagnostic/invoke"],
}}
```

When a runtime has this block, it accepts JWT bearer tokens only. IAM SigV4 calls are refused, even with admin
credentials. Identifiers (no secrets) are written to `.codeai-data/agentcore/state.json`, which git ignores.

## What `demo` shows

| Call | Result |
|---|---|
| No `Authorization` header | `401 Missing Authentication Token`, with a `WWW-Authenticate: Bearer resource_metadata=...` header that points to the protected-resource metadata |
| Forged token (right issuer, client, and scope; fake signature) | `403 OAuth authorization failed: Invalid Bearer token` |
| `bedrock-agentcore:InvokeAgentRuntime` signed with SigV4 | `AccessDeniedException: Authorization method mismatch` |
| Cognito access token | `200` with the `validate_submission` output |

The same rejection with curl:

```bash
ARN=$(python3 -c "import json;print(json.load(open('.codeai-data/agentcore/state.json'))['runtime_arn'])")
ENC=$(python3 -c "import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=''))" "$ARN")
curl -i -X POST "https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/$ENC/invocations?qualifier=DEFAULT" \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: $(python3 -c 'import uuid;print(uuid.uuid4())')" \
  -d '{"lesson_id":"weather-station-readiness","task_id":"repeat-explain","attempt_no":1,"submission_text":"hi","rubric_id":"WS-DIAG-v0.1-draft"}'
# HTTP/2 401
# {"jsonrpc":"2.0","error":{"code":-32001,"message":"Missing Authentication Token"}}
```

## Files

| File | What it does |
|---|---|
| `app.py` | The runtime entry point (`main.py` in the zip): `GET /ping` and `POST /invocations` on port 8080, standard library only. It contains no auth code because AgentCore checks the token first. Student text is never logged. |
| `package.py` | Builds the zip from `engine/`, `diagnostic/`, and `projects/weather-station/`, plus PyYAML vendored for Linux arm64 (AgentCore runs only on arm64). |
| `provision.py` | `deploy` and `destroy`: finds each resource by name and creates only what is missing. |
| `demo.py` | The four calls above. Tokens are never printed. |
| `settings.py` | Names, region, and the state file. |

Try the entry point locally with `PORT=8091 python3 -m deploy.agentcore.app`.

## Before production

- Use `"networkMode": "VPC"` instead of `PUBLIC`.
- Add `customClaims` (for example a school or role claim) if callers need finer rules than client and scope.
- Encrypt the `/aws/bedrock-agentcore/runtimes/...` log group with KMS and set a retention period.
- If a person, not a service, calls the runtime, use the authorization-code flow with a user pool app client in place of `client_credentials`.
