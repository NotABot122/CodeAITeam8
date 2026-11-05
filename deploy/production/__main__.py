"""Deploy CodeAI to production: one private EC2 instance behind CloudFront (see documentation/PRODUCTION.md).

    python -m deploy.production infra      create or update the two stacks and the production storage config
    python -m deploy.production release    build a release from the current commit, install it, smoke-test the URL
    python -m deploy.production status     the URL, the instance, and what /api/health says

Run from the repo root with the venv's Python and AWS credentials for the account (the admin role).
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
REGION = os.environ.get("CODEAI_AWS_REGION", "us-west-2")
STORAGE_STACK = "codeai-storage-prod"
APP_STACK = "codeai-prod"
PROD_CONFIG = ROOT / "config" / "aws_storage.prod.json"
SERVER_ROLE = "CodeAITeam8ProdServer-{region}"

# What a release contains: what the server needs to run, nothing else (no tests, evaluation data or specs).
RELEASE_PATHS = ("engine/", "webapi/", "diagnostic/", "projects/", "config/", "deploy/__init__.py",
                 "deploy/production/", "documentation/curriculum/", "README.md")


def say(text: str) -> None:
    print(text, flush=True)


def _boto(service: str):
    import boto3
    return boto3.client(service, region_name=REGION)


def _outputs(stack: str) -> Dict[str, str]:
    out = _boto("cloudformation").describe_stacks(StackName=stack)["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in out}


def _caller_role_arn() -> str:
    arn = _boto("sts").get_caller_identity()["Arn"]          # arn:aws:sts::<acct>:assumed-role/<role>/<session>
    if ":assumed-role/" not in arn:
        return arn
    account = arn.split(":")[4]
    return f"arn:aws:iam::{account}:role/{arn.split('/')[1]}"


def _cfn_deploy(stack: str, template: str, params: Dict[str, str]) -> None:
    say(f"Stack {stack} ({template}) ...")
    cmd = ["aws", "cloudformation", "deploy", "--region", REGION, "--stack-name", stack,
           "--template-file", str(ROOT / template), "--capabilities", "CAPABILITY_NAMED_IAM",
           "--no-fail-on-empty-changeset", "--tags", "project=codeai-team8", "environment=prod",
           "--parameter-overrides", *[f"{k}={v}" for k, v in params.items()]]
    subprocess.run(cmd, check=True)


def _storage_cli(*args: str) -> None:
    env = dict(os.environ, CODEAI_STORAGE_CONFIG=str(PROD_CONFIG), CODEAI_AWS_REGION=REGION)
    subprocess.run([sys.executable, "-m", "engine.s3_storage", *args], cwd=ROOT, env=env, check=True)


def cmd_infra(publish_curriculum: bool) -> int:
    admin = _caller_role_arn()
    account = admin.split(":")[4]
    server_role = f"arn:aws:iam::{account}:role/{SERVER_ROLE.format(region=REGION)}"
    _cfn_deploy(STORAGE_STACK, "infrastructure/curriculum-and-progress.yaml",
                {"Suffix": "-prod", "AppRunnerRoleArn": server_role, "KeyAdminRoleArn": admin})
    _storage_cli("configure", "--stack", STORAGE_STACK, "--region", REGION)
    config = json.loads(PROD_CONFIG.read_text())
    if publish_curriculum or not config.get("curriculum_version_id"):
        _storage_cli("publish-curriculum")
    storage = _outputs(STORAGE_STACK)
    params = {"AppRoleArn": storage["AppRoleArn"], "CloudFrontOriginGroup": _origin_group() or ""}
    _cfn_deploy(APP_STACK, "infrastructure/production.yaml", params)
    group = _origin_group()
    if group and group != params["CloudFrontOriginGroup"]:     # first deploy: CloudFront made its group just now
        say(f"Letting CloudFront's VPC origin group {group} reach the server ...")
        _cfn_deploy(APP_STACK, "infrastructure/production.yaml", dict(params, CloudFrontOriginGroup=group))
    app = _outputs(APP_STACK)
    say(f"Infrastructure ready. URL {app['Url']} (serves nothing until the first release).")
    say(f"Commit {PROD_CONFIG.relative_to(ROOT)} so releases carry the production storage settings.")
    return 0


def _origin_group() -> str:
    """The security group CloudFront creates in our VPC for the VPC origin, or '' before the stack exists."""
    try:
        vpc = _boto("ec2").describe_vpcs(Filters=[{"Name": "tag:Name", "Values": ["codeai-prod"]}])["Vpcs"]
    except Exception:
        return ""
    if not vpc:
        return ""
    groups = _boto("ec2").describe_security_groups(Filters=[
        {"Name": "vpc-id", "Values": [vpc[0]["VpcId"]]},
        {"Name": "group-name", "Values": ["CloudFront-VPCOrigins-Service-SG"]}])["SecurityGroups"]
    return groups[0]["GroupId"] if groups else ""


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _build_release(allow_dirty: bool) -> (str, bytes):
    if _git("status", "--porcelain") and not allow_dirty:
        raise SystemExit("The working tree has uncommitted changes. Commit them (a release is a commit) or pass "
                         "--allow-dirty for a test release.")
    if not PROD_CONFIG.exists():
        raise SystemExit("No config/aws_storage.prod.json: run `python -m deploy.production infra` first.")
    sha = _git("rev-parse", "--short=10", "HEAD") + ("-dirty" if allow_dirty and _git("status", "--porcelain") else "")
    release = f"{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}-{sha}"
    say("Building the student UI ...")
    env = dict(os.environ, VITE_API_BASE_URL=".")
    subprocess.run(["npm", "run", "-s", "build", "--", "--base", "./"], cwd=ROOT / "frontend", env=env, check=True,
                   stdout=subprocess.DEVNULL)
    files = [f for f in _git("ls-files").splitlines() if f.startswith(RELEASE_PATHS)]
    if str(PROD_CONFIG.relative_to(ROOT)) not in files:
        files.append(str(PROD_CONFIG.relative_to(ROOT)))       # allowed before it is committed, with a warning
        say("Note: config/aws_storage.prod.json is not committed yet; including the working copy.")
    dist = ROOT / "frontend" / "dist"
    files += [str(p.relative_to(ROOT)) for p in sorted(dist.rglob("*")) if p.is_file()]
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name in files:
            path = ROOT / name
            if path.is_file():
                tar.add(path, arcname=name)
        info = tarfile.TarInfo("RELEASE")
        data = json.dumps({"release": release, "commit": _git("rev-parse", "HEAD"),
                           "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}).encode()
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return release, buffer.getvalue()


def _wait_for_ssm(instance_id: str, timeout_s: int = 600) -> None:
    ssm = _boto("ssm")
    end = time.time() + timeout_s
    while time.time() < end:
        info = ssm.describe_instance_information(Filters=[{"Key": "InstanceIds", "Values": [instance_id]}])
        if any(i.get("PingStatus") == "Online" for i in info.get("InstanceInformationList", [])):
            return
        time.sleep(10)
    raise SystemExit(f"The instance {instance_id} never came online in Systems Manager.")


def _run_on_instance(instance_id: str, commands: List[str], timeout_s: int = 1500) -> str:
    ssm = _boto("ssm")
    command_id = ssm.send_command(
        InstanceIds=[instance_id], DocumentName="AWS-RunShellScript", Comment="CodeAI release",
        Parameters={"commands": commands, "executionTimeout": [str(timeout_s)]}, TimeoutSeconds=600,
    )["Command"]["CommandId"]
    end = time.time() + timeout_s + 60
    while time.time() < end:
        time.sleep(5)
        try:
            inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if inv["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
            output = (inv.get("StandardOutputContent") or "") + (inv.get("StandardErrorContent") or "")
            if inv["Status"] != "Success":
                raise SystemExit(f"Install on the instance {inv['Status'].lower()}:\n{output[-4000:]}")
            return output
    raise SystemExit("The install on the instance did not finish in time.")


def _health(url: str, tries: int = 30) -> dict:
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=15) as response:
                return json.load(response)
        except Exception as exc:                 # CloudFront may still be propagating
            last = exc
            time.sleep(10)
    raise SystemExit(f"{url}/api/health did not answer: {last}")


def cmd_release(allow_dirty: bool) -> int:
    app = _outputs(APP_STACK)
    release, body = _build_release(allow_dirty)
    key = f"releases/{release}.tar.gz"
    say(f"Uploading {key} ({len(body) // 1024} KiB) ...")
    _boto("s3").put_object(Bucket=app["ReleaseBucketName"], Key=key, Body=body)
    _boto("ssm").put_parameter(Name=app["ReleaseParameter"], Value=key, Type="String", Overwrite=True)
    _wait_for_ssm(app["InstanceId"])
    say(f"Installing on {app['InstanceId']} ...")
    output = _run_on_instance(app["InstanceId"], [
        "set -euo pipefail",
        f"aws s3 cp --region {REGION} --quiet s3://{app['ReleaseBucketName']}/{key} /root/codeai-release.tar.gz",
        "rm -rf /root/codeai-release && mkdir /root/codeai-release",
        "tar -xzf /root/codeai-release.tar.gz -C /root/codeai-release",
        f"bash /root/codeai-release/deploy/production/install.sh /root/codeai-release.tar.gz {release}",
    ])
    for line in output.strip().splitlines()[-4:]:
        say("  " + line)
    health = _health(app["Url"])
    say(f"Live at {app['Url']}: AI {'on' if health.get('ai') else 'off'}, safety {health.get('safety')}, "
        f"storage {health.get('storage')}, dev {health.get('dev')}")
    if health.get("dev") or not str(health.get("storage", "")).startswith("S3"):
        say("WARNING: production should have dev off and S3 storage on.")
        return 1
    return 0


def cmd_status() -> int:
    app = _outputs(APP_STACK)
    state = _boto("ec2").describe_instances(InstanceIds=[app["InstanceId"]])["Reservations"][0]["Instances"][0]["State"]["Name"]
    say(f"URL {app['Url']}\ninstance {app['InstanceId']} ({state})")
    try:
        say("release " + _boto("ssm").get_parameter(Name=app["ReleaseParameter"])["Parameter"]["Value"])
    except Exception:
        say("release: none yet")
    say("health " + json.dumps(_health(app["Url"], tries=2)))
    say(f"teacher token: aws secretsmanager get-secret-value --region {REGION} --secret-id "
        f"{app['TeacherTokenSecret'].split(':')[-1].rsplit('-', 1)[0]} --query SecretString --output text")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m deploy.production")
    sub = parser.add_subparsers(dest="cmd", required=True)
    infra = sub.add_parser("infra", help="create or update the production stacks")
    infra.add_argument("--publish-curriculum", action="store_true", help="upload and pin the standards JSON again")
    rel = sub.add_parser("release", help="build, upload and install a release, then smoke-test it")
    rel.add_argument("--allow-dirty", action="store_true", help="release uncommitted changes (testing only)")
    sub.add_parser("status", help="URL, instance state, release and health")
    args = parser.parse_args(argv)
    if args.cmd == "infra":
        return cmd_infra(args.publish_curriculum)
    if args.cmd == "release":
        return cmd_release(args.allow_dirty)
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main())
