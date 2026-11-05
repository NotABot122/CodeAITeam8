#!/bin/bash
# Install or update CodeAI on the production instance (Amazon Linux 2023). Run as root:
#     install.sh <release.tar.gz> <release-id>
# Safe to run again: each step checks what is already there. Called by the instance's first boot (user data) and by
# `python -m deploy.production release` through SSM Run Command.
#
#   codeai           the service user. Owns /var/lib/codeai (student data's working copy, 0700).
#   codeai-sandbox   runs student code (engine/grader.py through sudo and run-student-code). No network: an
#                    nftables rule drops every packet it sends. Can't read /var/lib/codeai or /etc/codeai.
set -euo pipefail

TARBALL=$1
RELEASE=$2
APP_USER=codeai
SANDBOX_USER=codeai-sandbox
BASE=/opt/codeai
DATA=/var/lib/codeai
ETC=/etc/codeai
REGION=$(TOKEN=$(curl -sf -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60') &&
         curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
SECRET_ID=codeai-team8/prod/teacher-token
say() { echo "[codeai install] $*"; }
exec 9>/run/codeai-install.lock
flock 9                      # first boot and a pushed release can arrive together; one install at a time

# 1. Packages ---------------------------------------------------------------------------------------------------
PY=""
for v in 3.12 3.11; do
  if command -v python$v >/dev/null || dnf install -y -q python$v python$v-pip >/dev/null 2>&1; then PY=python$v; break; fi
done
[ -n "$PY" ] || { echo "no python 3.11 or 3.12 available" >&2; exit 1; }
rpm -q nftables >/dev/null || dnf install -y -q nftables
say "python: $($PY --version)"

# 2. Users and folders ---------------------------------------------------------------------------------------------
id $APP_USER >/dev/null 2>&1 || useradd --system --home-dir $DATA --no-create-home --shell /sbin/nologin $APP_USER
id $SANDBOX_USER >/dev/null 2>&1 || useradd --system --home-dir /nonexistent --no-create-home --shell /sbin/nologin $SANDBOX_USER
install -d -m 0755 -o root -g root $BASE $BASE/releases $BASE/bin
install -d -m 0700 -o $APP_USER -g $APP_USER $DATA
install -d -m 0750 -o root -g $APP_USER $ETC

# 3. The release: read-only for everyone but root ----------------------------------------------------------------
[ -x $BASE/venv/bin/python ] && $BASE/venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' ||
  { rm -rf $BASE/venv; $PY -m venv $BASE/venv; }
DEST=$BASE/releases/$RELEASE
if [ ! -d "$DEST" ]; then
  rm -rf "$DEST.partial" && mkdir "$DEST.partial"
  tar -xzf "$TARBALL" -C "$DEST.partial"
  $BASE/venv/bin/pip install -q --disable-pip-version-check -r "$DEST.partial/deploy/production/requirements.txt"
  # Each project's weather database is built from its seed on first use, inside the project folder. The release is
  # read-only to the service, so build them all now.
  (cd "$DEST.partial" && PYTHONPATH=. $BASE/venv/bin/python -c '
from pathlib import Path
from engine.project import load_project
for folder in sorted(Path("projects").iterdir()):
    if (folder / "manifest.yaml").exists():
        load_project(folder).ensure_dataset()
')
  chown -R root:root "$DEST.partial"
  find "$DEST.partial" -type d -exec chmod 0755 {} + ; find "$DEST.partial" -type f -exec chmod 0644 {} +
  mv "$DEST.partial" "$DEST"
fi
$BASE/venv/bin/pip install -q --disable-pip-version-check -r "$DEST/deploy/production/requirements.txt"

# 4. Student-code sandbox ------------------------------------------------------------------------------------------
install -m 0755 -o root -g root "$DEST/deploy/production/run-student-code" $BASE/bin/run-student-code
cat > /etc/sudoers.d/codeai <<EOF
# The CodeAI service may run the grading wrapper as the sandbox user, and nothing else.
Defaults:$APP_USER !requiretty, !syslog
$APP_USER ALL=($SANDBOX_USER) NOPASSWD: $BASE/bin/run-student-code
EOF
chmod 0440 /etc/sudoers.d/codeai
visudo -cf /etc/sudoers.d/codeai >/dev/null
install -d -m 0755 /etc/nftables
cat > /etc/nftables/codeai-sandbox.nft <<EOF
# Student code gets no network at all: not the internet, not instance metadata, not this server.
# (The first two lines make reloading this file replace the table instead of adding a second rule.)
table inet codeai_sandbox
delete table inet codeai_sandbox
table inet codeai_sandbox {
  chain output {
    type filter hook output priority 0; policy accept;
    meta skuid "$SANDBOX_USER" counter drop
  }
}
EOF
grep -q codeai-sandbox.nft /etc/sysconfig/nftables.conf 2>/dev/null || echo 'include "/etc/nftables/codeai-sandbox.nft"' >> /etc/sysconfig/nftables.conf
systemctl enable -q nftables
nft -f /etc/nftables/codeai-sandbox.nft

# 5. Settings: the teacher token comes from Secrets Manager and stays in a root:codeai 0640 file ---------------------
TEACHER_TOKEN=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id $SECRET_ID --query SecretString --output text)
umask 027
cat > $ETC/env.new <<EOF
CODEAI_TEACHER_TOKEN=$TEACHER_TOKEN
CODEAI_STORAGE_CONFIG=$BASE/app/config/aws_storage.prod.json
CODEAI_SANDBOX_COMMAND=$BASE/bin/run-student-code
CODEAI_SANDBOX_USER=$SANDBOX_USER
CODEAI_AWS_REGION=$REGION
AWS_REGION=$REGION
AWS_DEFAULT_REGION=$REGION
EOF
umask 022
chown root:$APP_USER $ETC/env.new && chmod 0640 $ETC/env.new && mv $ETC/env.new $ETC/env
unset TEACHER_TOKEN

# 6. Service ------------------------------------------------------------------------------------------------------
install -m 0644 -o root -g root "$DEST/deploy/production/codeai.service" /etc/systemd/system/codeai.service
ln -sfn "$DEST" $BASE/app.new && mv -T $BASE/app.new $BASE/app
systemctl daemon-reload
systemctl enable -q codeai
systemctl restart codeai
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8080/api/health >/dev/null; then
    say "release $RELEASE is running: $(curl -sf http://127.0.0.1:8080/api/health)"
    # Keep the three newest releases, and always the one now running (a rollback may be older).
    for old in $(ls -1dt $BASE/releases/*/ | tail -n +4); do
      [ "$(realpath "$old")" = "$(realpath "$DEST")" ] || rm -rf "$old"
    done
    exit 0
  fi
  sleep 1
done
echo "the service did not answer on port 8080 within 60 seconds" >&2
journalctl -u codeai -n 40 --no-pager >&2
exit 1
