"""Names, region, and the local state file shared by the deploy and demo commands."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Optional

from engine import REPO_ROOT

REGION = os.environ.get("CODEAI_AWS_REGION", "us-west-2")
PREFIX = "codeai-team8"

RUNTIME_NAME = "codeai_team8_diagnostic"          # [a-zA-Z][a-zA-Z0-9_]{0,47}
RUNTIME_PYTHON = "PYTHON_3_12"
ROLE_NAME = "CodeAITeam8DiagnosticRuntime"
USER_POOL_NAME = f"{PREFIX}-agentcore"
CLIENT_NAME = f"{PREFIX}-diagnostic-caller"
RESOURCE_SERVER_ID = "codeai-diagnostic"
SCOPE = f"{RESOURCE_SERVER_ID}/invoke"

STATE_FILE = REPO_ROOT / ".codeai-data" / "agentcore" / "state.json"   # .codeai-data/ is git-ignored


def bucket_name(account_id: str) -> str:
    return f"{PREFIX}-agentcore-code-{account_id}-{REGION}"


def cognito_domain(account_id: str) -> str:
    """Hosted-domain prefix; must be unique across all of Cognito in the region."""
    return f"{PREFIX}-{account_id}"


@dataclass
class State:
    """Identifiers of what `deploy` created. No secrets: the client secret stays in Cognito."""

    region: str = REGION
    account_id: str = ""
    user_pool_id: str = ""
    client_id: str = ""
    domain: str = ""
    bucket: str = ""
    code_key: str = ""
    role_arn: str = ""
    runtime_id: str = ""
    runtime_arn: str = ""

    @property
    def discovery_url(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/openid-configuration"

    @property
    def token_url(self) -> str:
        return f"https://{self.domain}.auth.{self.region}.amazoncognito.com/oauth2/token"

    def save(self, path: Path = STATE_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path = STATE_FILE) -> Optional["State"]:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{f.name: data[f.name] for f in fields(cls) if f.name in data})
