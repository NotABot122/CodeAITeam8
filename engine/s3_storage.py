"""Student data in a private S3 bucket, with the local data directory as the working copy.

The engine, the readiness check and the web API keep reading and writing files under the data directory
(.codeai-data/ by default). When S3 storage is on, every file they change is copied to the student-data bucket
in the background (within about a second), and on start the server restores the directory from the bucket.
So progress survives losing the machine. One server at a time: two servers would each keep their own copy.

What is copied: progress/ (lesson progress, profiles, readiness-check state), workspace/ (student code),
themes/ ("Make it yours" projects) and logs/ (pseudonymous event logs). Never: temporary files, caches,
generated databases, or anything else in the data directory.

Access: every S3 call uses the app role from infrastructure/curriculum-and-progress.yaml, the only principal the
bucket policy and the KMS key let read or write student data. Settings come from config/aws_storage.json
(written by `python -m engine.s3_storage configure`) or the environment:

    CODEAI_STUDENT_DATA_BUCKET   bucket name (S3 storage is off when it is unset)
    CODEAI_APP_ROLE_ARN          role to assume for S3 (the curriculum loader uses it too)
    CODEAI_AWS_REGION            region (default us-west-2)
    CODEAI_S3_STORAGE=off        turn S3 storage off even when the config file exists
    CODEAI_STORAGE_CONFIG        another config file (production: config/aws_storage.prod.json)

Commands:
    python -m engine.s3_storage configure [--stack codeai-storage]   write config/aws_storage.json from the stack
    python -m engine.s3_storage publish-curriculum                    upload the standards JSON, pin its version
    python -m engine.s3_storage status                                what is in the bucket (counts only)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import stat
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "aws_storage.json"
CURRICULUM_FILE = ROOT / "documentation" / "curriculum" / "csta-standards.json"
CURRICULUM_KEY = "standards/csta.json"
DEFAULT_REGION = "us-west-2"
DEFAULT_STACK = "codeai-storage"

MIRRORED = ("progress", "workspace", "themes", "logs")      # top-level folders of the data directory
SKIP_PARTS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".db", ".tmp"}
DEBOUNCE_S = 0.5
MAX_BACKOFF_S = 60.0


# Settings ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StorageConfig:
    bucket: str
    region: str = DEFAULT_REGION
    role_arn: Optional[str] = None
    curriculum_uri: Optional[str] = None
    curriculum_version_id: Optional[str] = None


def config_path() -> Path:
    """config/aws_storage.json, or the file CODEAI_STORAGE_CONFIG names (production uses its own)."""
    return Path(os.environ.get("CODEAI_STORAGE_CONFIG") or CONFIG)


def load_config() -> Optional[StorageConfig]:
    """S3 storage settings from the environment, then config/aws_storage.json. None when S3 storage is off."""
    if os.environ.get("CODEAI_S3_STORAGE", "").lower() in ("off", "0", "false", "no"):
        return None
    data: Dict[str, Any] = {}
    try:
        data = json.loads(config_path().read_text())
    except (OSError, ValueError):
        pass
    bucket = os.environ.get("CODEAI_STUDENT_DATA_BUCKET") or data.get("student_data_bucket")
    if not bucket:
        return None
    return StorageConfig(
        bucket=bucket,
        region=os.environ.get("CODEAI_AWS_REGION") or data.get("region") or DEFAULT_REGION,
        role_arn=os.environ.get("CODEAI_APP_ROLE_ARN") or data.get("app_role_arn"),
        curriculum_uri=data.get("curriculum_uri"),
        curriculum_version_id=data.get("curriculum_version_id"),
    )


def apply_curriculum_settings(cfg: StorageConfig) -> None:
    """Point the curriculum loader at the pinned S3 copy, unless the environment already chose a source."""
    if cfg.curriculum_uri and cfg.curriculum_version_id and not os.environ.get("CODEAI_CURRICULUM"):
        os.environ["CODEAI_CURRICULUM"] = cfg.curriculum_uri
        os.environ["CODEAI_CURRICULUM_VERSION_ID"] = cfg.curriculum_version_id
    if cfg.role_arn:
        os.environ.setdefault("CODEAI_APP_ROLE_ARN", cfg.role_arn)
    os.environ.setdefault("CODEAI_AWS_REGION", cfg.region)


# The app role ----------------------------------------------------------------------------------------------------

_sessions: Dict[Tuple[str, str], Any] = {}
_sessions_lock = threading.Lock()


def _app_session(role_arn: str, region: str):
    """A boto3 session that assumes the app role and refreshes its credentials before they expire."""
    import boto3
    import botocore.session
    from botocore.credentials import CredentialProvider, DeferredRefreshableCredentials

    def fetch() -> Dict[str, str]:
        creds = boto3.client("sts", region_name=region).assume_role(
            RoleArn=role_arn, RoleSessionName="codeai-app", DurationSeconds=3600)["Credentials"]
        return {"access_key": creds["AccessKeyId"], "secret_key": creds["SecretAccessKey"],
                "token": creds["SessionToken"], "expiry_time": creds["Expiration"].isoformat()}

    class AppRole(CredentialProvider):
        METHOD = "codeai-app-role"

        def load(self):
            return DeferredRefreshableCredentials(fetch, self.METHOD)

    core = botocore.session.Session()
    core.get_component("credential_provider").insert_before("env", AppRole())
    return boto3.Session(botocore_session=core, region_name=region)


def app_client(service: str, region: Optional[str] = None, role_arn: Optional[str] = None):
    """An AWS client as the app role (CODEAI_APP_ROLE_ARN) when one is set, else the default credentials."""
    region = region or os.environ.get("CODEAI_AWS_REGION") or DEFAULT_REGION
    role_arn = role_arn or os.environ.get("CODEAI_APP_ROLE_ARN")
    from botocore.config import Config
    config = Config(retries={"max_attempts": 5, "mode": "standard"}, connect_timeout=5, read_timeout=20)
    if not role_arn:
        import boto3
        return boto3.client(service, region_name=region, config=config)
    with _sessions_lock:
        session = _sessions.get((role_arn, region))
        if session is None:
            session = _sessions[(role_arn, region)] = _app_session(role_arn, region)
    return session.client(service, config=config)


# Local protection -----------------------------------------------------------------------------------------------

def lock_down(data_dir: Path) -> None:
    """Only the server's own OS user can read the data directory: new files 0600, folders 0700, and existing
    ones tightened. Student data never needs to be readable by other accounts on the machine."""
    os.umask(0o077)
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for path in [data_dir, *data_dir.rglob("*")]:
        try:
            if path.is_symlink():
                continue
            mode = stat.S_IMODE(path.stat().st_mode)
            wanted = mode & 0o700 if path.is_file() else 0o700
            if mode != wanted:
                os.chmod(path, wanted)
        except OSError:
            pass


# The mirror ----------------------------------------------------------------------------------------------------

def _mirrored(rel: Path) -> bool:
    parts = rel.parts
    return (bool(parts) and parts[0] in MIRRORED and not SKIP_PARTS & set(parts)
            and not any(p.startswith(".") for p in parts) and rel.suffix not in SKIP_SUFFIXES)


class S3Mirror:
    """Copies changed files under `root` to s3://bucket/<relative path>, in a background thread.

    A small manifest (<root>/.s3-sync.json, never uploaded) remembers the size and modification time of each
    file when it was last saved to S3, so a restart re-sends exactly the files that changed since."""

    def __init__(self, root: Path, bucket: str, client: Any, debounce_s: float = DEBOUNCE_S):
        self.root = Path(root).resolve()
        self.bucket = bucket
        self.client = client
        self.debounce_s = debounce_s
        self._due: Dict[str, Tuple[float, str]] = {}       # key -> (when, "put" | "delete" | "folder")
        self._failures: Dict[str, int] = {}
        self._busy = 0
        self._cond = threading.Condition()
        self._stop = False
        self._manifest_path = self.root / ".s3-sync.json"
        self._manifest: Dict[str, List[int]] = self._load_manifest()
        self._manifest_dirty = False
        self.uploaded = 0
        self.last_error: Optional[str] = None
        self._thread = threading.Thread(target=self._run, name="s3-mirror", daemon=True)
        self._thread.start()

    # Manifest ----------------------------------------------------------------------------------------------------
    def _load_manifest(self) -> Dict[str, List[int]]:
        try:
            data = json.loads(self._manifest_path.read_text())
            return {k: list(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _save_manifest(self) -> None:
        with self._cond:
            if not self._manifest_dirty:
                return
            data = json.dumps(self._manifest, sort_keys=True)
            self._manifest_dirty = False
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.root), prefix=".s3-sync-")
        with os.fdopen(fd, "w") as handle:
            handle.write(data)
        os.replace(tmp, self._manifest_path)

    def _note(self, key: str, st: Optional[os.stat_result]) -> None:
        with self._cond:
            if st is None:
                self._manifest.pop(key, None)
            else:
                self._manifest[key] = [st.st_mtime_ns, st.st_size]
            self._manifest_dirty = True

    def _in_sync(self, key: str, path: Path) -> bool:
        st = path.stat()
        return self._manifest.get(key) == [st.st_mtime_ns, st.st_size]

    # What writers call -----------------------------------------------------------------------------------------
    def _key(self, path: Path) -> Optional[str]:
        try:
            rel = Path(os.path.abspath(path)).relative_to(self.root)
        except ValueError:
            return None
        return rel.as_posix() if _mirrored(rel) else None

    def _queue(self, key: str, op: str) -> None:
        with self._cond:
            self._due[key] = (time.monotonic() + self.debounce_s, op)
            self._cond.notify()

    def changed(self, path: Path) -> None:
        path = Path(path)
        if path.is_dir():
            children = [c for c in path.rglob("*") if c.is_file()]
            key = self._key(path)
            if not children and key is not None:
                self._queue(key + "/", "folder")          # an empty folder: a new student with nothing saved yet
            for child in children:
                self.changed(child)
            return
        key = self._key(path)
        if key is not None:
            self._queue(key, "put")

    def removed(self, path: Path) -> None:
        key = self._key(Path(path))
        if key is not None:
            self._queue(key, "delete")

    # Background work -------------------------------------------------------------------------------------------
    def _do(self, key: str, op: str) -> None:
        if op == "folder":
            self.client.put_object(Bucket=self.bucket, Key=key, Body=b"")
        elif op == "delete":
            self.client.delete_object(Bucket=self.bucket, Key=key)
            self._note(key, None)
        else:
            path = self.root / key
            try:
                st = path.stat()
                body = path.read_bytes()
            except FileNotFoundError:
                return                              # replaced or moved since; its new name is queued
            self.client.put_object(Bucket=self.bucket, Key=key, Body=body)
            self._note(key, st)

    def _run(self) -> None:
        while True:
            with self._cond:
                while True:
                    now = time.monotonic()
                    ready = [(k, op) for k, (when, op) in self._due.items() if when <= now]
                    if ready or (self._stop and not self._due):
                        break
                    wait = min((when for when, _ in self._due.values()), default=now + 3600) - now
                    self._cond.wait(timeout=max(0.05, wait))
                if not ready and self._stop:
                    return
                for k, _ in ready:
                    del self._due[k]
                self._busy = len(ready)
            for key, op in ready:
                try:
                    self._do(key, op)
                    self.uploaded += 1
                    self._failures.pop(key, None)
                except Exception as exc:                   # keep it and retry with backoff
                    n = self._failures[key] = self._failures.get(key, 0) + 1
                    self.last_error = f"{type(exc).__name__} on {op} ({n} tries)"
                    with self._cond:
                        if key not in self._due:
                            self._due[key] = (time.monotonic() + min(MAX_BACKOFF_S, 2.0 ** n), op)
                with self._cond:
                    self._busy -= 1
                    self._cond.notify_all()
            try:
                self._save_manifest()
            except OSError:
                pass

    def pending(self) -> int:
        with self._cond:
            return len(self._due) + self._busy

    def flush(self, timeout: float = 20.0) -> bool:
        """Send everything queued now (skipping the debounce). True if nothing is left."""
        end = time.monotonic() + timeout
        with self._cond:
            self._due = {k: (0.0, op) for k, (_, op) in self._due.items()}
            self._cond.notify_all()
            while (self._due or self._busy) and time.monotonic() < end:
                if not self._busy and all(when > time.monotonic() for when, _ in self._due.values()):
                    break                                   # only failing items left, waiting on backoff
                self._cond.wait(timeout=0.1)
            return not self._due and not self._busy

    def close(self, timeout: float = 20.0) -> bool:
        done = self.flush(timeout)
        with self._cond:
            self._stop = True
            self._cond.notify_all()
        self._thread.join(timeout=2)
        return done

    # Start-up sync -----------------------------------------------------------------------------------------------
    def restore(self) -> Dict[str, int]:
        """Make the data directory and the bucket agree. Files only in S3 are downloaded (a new or wiped
        machine). Local files that changed since they were last saved, or that S3 lacks, are queued (data
        written while S3 was unreachable, or before S3 storage was turned on). The local copy wins otherwise."""
        remote = set()
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket):
            remote.update(obj["Key"] for obj in page.get("Contents", []))
        downloaded = folders = queued = 0
        for key in sorted(remote):
            rel = Path(key)
            if ".." in rel.parts or rel.is_absolute() or not _mirrored(rel):
                continue
            path = self.root / rel
            if key.endswith("/"):
                path.mkdir(parents=True, exist_ok=True)
                folders += 1
                continue
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".restore-")
            with os.fdopen(fd, "wb") as handle:
                handle.write(body)
            os.replace(tmp, path)
            self._note(key, path.stat())
            downloaded += 1
        for top in MIRRORED:
            base = self.root / top
            if not base.is_dir():
                continue
            for path in base.rglob("*"):
                key = self._key(path)
                if key is None:
                    continue
                if path.is_dir():
                    if not any(path.iterdir()) and key + "/" not in remote:
                        self._queue(key + "/", "folder")
                        queued += 1
                elif key not in remote or not self._in_sync(key, path):
                    self._queue(key, "put")
                    queued += 1
        self._save_manifest()
        return {"downloaded": downloaded, "folders": folders, "queued": queued, "in_bucket": len(remote)}

    def describe(self) -> str:
        left = self.pending()
        text = f"S3 s3://{self.bucket} ({self.uploaded} saved, {left} waiting)"
        return text + (f", last error: {self.last_error}" if self.last_error and left else "")


# Hooks the writers call. No-ops unless the server turned S3 storage on. ------------------------------------------

_mirror: Optional[S3Mirror] = None


def use(mirror: Optional[S3Mirror]) -> None:
    global _mirror
    _mirror = mirror


def current() -> Optional[S3Mirror]:
    return _mirror


def changed(path) -> None:
    """A file (or a folder and everything in it) under the data directory was written."""
    if _mirror is not None:
        _mirror.changed(Path(path))


def moved(old, new) -> None:
    if _mirror is not None:
        _mirror.removed(Path(old))
        _mirror.changed(Path(new))


def start(data_dir: Path, cfg: StorageConfig, client: Any = None) -> Tuple[S3Mirror, Dict[str, int]]:
    """Restore the data directory from the bucket and copy every later change to it."""
    client = client or app_client("s3", cfg.region, cfg.role_arn)
    mirror = S3Mirror(Path(data_dir), cfg.bucket, client)
    summary = mirror.restore()
    use(mirror)
    return mirror, summary


# Commands --------------------------------------------------------------------------------------------------------

def _write_config(data: Dict[str, Any]) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps(data, indent=2) + "\n")


def _read_config() -> Dict[str, Any]:
    try:
        return json.loads(config_path().read_text())
    except (OSError, ValueError):
        return {}


def cmd_configure(stack: str, region: str) -> int:
    import boto3
    outputs = boto3.client("cloudformation", region_name=region).describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]
    out = {o["OutputKey"]: o["OutputValue"] for o in outputs}
    data = _read_config()
    data.update({
        "region": region,
        "stack": stack,
        "student_data_bucket": out["StudentDataBucketName"],
        "app_role_arn": out["AppRoleArn"],
        "student_data_key_arn": out["StudentDataKeyArn"],
        "curriculum_bucket": out["CurriculumBucketName"],
        "curriculum_uri": f"s3://{out['CurriculumBucketName']}/{CURRICULUM_KEY}",
    })
    _write_config(data)
    print(f"Wrote {config_path()}: bucket {data['student_data_bucket']}, role {data['app_role_arn']}")
    return 0


def cmd_publish_curriculum() -> int:
    """Upload the reviewed standards JSON (as the person running this, the curriculum publisher) and pin it."""
    import boto3
    from .curriculum import Curriculum
    data = _read_config()
    if not data.get("curriculum_bucket"):
        print("Run `python -m engine.s3_storage configure` first.", file=sys.stderr)
        return 1
    body = CURRICULUM_FILE.read_bytes()
    count = len(Curriculum.from_json(body).standards)          # refuse to publish a file that won't load
    s3 = boto3.client("s3", region_name=data["region"])
    version = s3.put_object(Bucket=data["curriculum_bucket"], Key=CURRICULUM_KEY, Body=body,
                            ContentType="application/json")["VersionId"]
    data["curriculum_version_id"] = version
    data["curriculum_published_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    _write_config(data)
    print(f"Published {count} standards to {data['curriculum_uri']} (version {version}); pinned in "
          f"{config_path()}.")
    return 0


def cmd_status() -> int:
    cfg = load_config()
    if cfg is None:
        print("S3 storage is off (no config/aws_storage.json or CODEAI_STUDENT_DATA_BUCKET).")
        return 1
    client = app_client("s3", cfg.region, cfg.role_arn)
    counts: Dict[str, int] = {}
    students = set()
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=cfg.bucket):
        for obj in page.get("Contents", []):
            parts = obj["Key"].split("/")
            counts[parts[0]] = counts.get(parts[0], 0) + 1
            if parts[0] in ("progress", "workspace") and len(parts) > 1:
                students.add(parts[1])
    summary = ", ".join(f"{k} {v} objects" for k, v in sorted(counts.items())) or "empty"
    print(f"s3://{cfg.bucket} as {cfg.role_arn or 'default credentials'}: {len(students)} students; {summary}")
    if cfg.curriculum_uri:
        print(f"curriculum: {cfg.curriculum_uri} version {cfg.curriculum_version_id or '(not published)'}")
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.s3_storage")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("configure", help="write config/aws_storage.json from the CloudFormation stack's outputs")
    c.add_argument("--stack", default=DEFAULT_STACK)
    c.add_argument("--region", default=os.environ.get("CODEAI_AWS_REGION") or DEFAULT_REGION)
    sub.add_parser("publish-curriculum", help="upload the standards JSON to the curriculum bucket and pin its version")
    sub.add_parser("status", help="count what is stored in the student-data bucket")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.cmd == "configure":
        return cmd_configure(args.stack, args.region)
    if args.cmd == "publish-curriculum":
        return cmd_publish_curriculum()
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main())
