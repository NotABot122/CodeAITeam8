# AWS storage (S3)

The app stores three things in S3:

| What | Where | Who can read it |
|---|---|---|
| Student data: progress, readiness-check answers, code, built themes, event logs | `codeai-team8-student-data-<account>-<region>`, encrypted with the KMS key `alias/codeai-team8-student-data` | Only the app role `CodeAITeam8App-<region>` |
| CSTA standards (curriculum), one pinned object version | `codeai-team8-curriculum-<account>-<region>`, `standards/csta.json` | The app role reads; the person publishing uploads |
| The readiness check's AgentCore deployment package (code, no student data) | `codeai-team8-agentcore-code-<account>-<region>` (made by `python -m deploy.agentcore deploy`) | The AgentCore runtime role |

The first two come from [infrastructure/curriculum-and-progress.yaml](../infrastructure/curriculum-and-progress.yaml). The third is
made by [deploy/agentcore/provision.py](../deploy/agentcore/provision.py) (see [its README](../deploy/agentcore/README.md)).

## Set it up

Run these as the account's admin role (here `WSParticipantRole`), in `us-west-2`, from the repo root.

```sh
ROLE=$(aws sts get-caller-identity --query Arn --output text | sed -E 's#:sts::([0-9]+):assumed-role/([^/]+)/.*#:iam::\1:role/\2#')
aws cloudformation deploy --stack-name codeai-storage --region us-west-2 \
  --template-file infrastructure/curriculum-and-progress.yaml --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides AppRunnerRoleArn=$ROLE KeyAdminRoleArn=$ROLE --tags project=codeai-team8
~/.venvs/codeai/bin/python -m engine.s3_storage configure            # writes config/aws_storage.json
~/.venvs/codeai/bin/python -m engine.s3_storage publish-curriculum   # uploads the standards JSON, pins the version
```

- **`AppRunnerRoleArn`** is the role the server runs as. It is the only principal that can assume the app role.
- **`KeyAdminRoleArn`** is the role that manages the KMS key. It must be the role deploying the stack.

Restart the server. It prints `Student data: s3://...` and `/api/health` shows `storage`. On its first start it uploads
what is already in `.codeai-data/`. `python -m engine.s3_storage status` counts what is in the bucket, as the app
role. Set `CODEAI_S3_STORAGE=off` to run on local disk only.

The KMS key costs about $1 a month. Storage and requests for a class are a few cents.

## How it works

`.codeai-data/` stays the server's working copy: the engine, the readiness check and the grader read and write files
there, as before. [engine/s3_storage.py](../engine/s3_storage.py) copies each changed file to the student-data
bucket in a background thread, about half a second after the write. A stop (Ctrl-C or SIGTERM) waits for the queue
to empty. On start the server restores the folder from the bucket:

- Files that exist only in S3 are downloaded (a new or wiped machine).
- Local files that changed since they were last saved are re-sent (from a crash or an S3 outage). A manifest,
  `.codeai-data/.s3-sync.json`, keeps track of this and is never uploaded.

If S3 can't be reached at start, the server runs on local disk and says so. If S3 fails while running, changes wait
and are retried, and `/api/health` shows how many are waiting. Run one server per bucket. Two servers would each keep
their own working copy.

Copied: `progress/`, `workspace/`, `themes/` and `logs/`. Not copied: temporary files, `__pycache__`, generated
`.db` files (rebuilt from their seed), and `agentcore/`.

The curriculum is read once per server start from the pinned version (`CODEAI_CURRICULUM` and
`CODEAI_CURRICULUM_VERSION_ID`, set from the config file). Publishing a new version does not change a running server
until the config is updated and the server restarts. If the S3 copy can't be read, the pathway is chosen without
standards (`CurriculumError`), and the server never falls back to the local file silently.

## What is stored about a student

| Data | Personal details? |
|---|---|
| Student id | A random 32-character id. No name, email, school or login. |
| Grade, buddy, goal, stages, attempts, hints, mistakes, pathway | No. |
| Interests ("What are you into?", up to 80 characters) | Dropped if it has an email, a phone number, "my name is", "I live", "my school is" and similar, or blocked words. |
| What they told the guide (readiness check) | The same check. A flagged answer is not stored, only that it was flagged. |
| "Make it yours" request | Screened by the Bedrock Guardrail, which blocks email, phone and address details, and by the local rules. |
| Code | Email addresses and phone numbers are replaced with `[removed]` before the file is saved, and the student is told why. |
| Event logs | Lesson events: allow-listed fields only, with the pseudonymous id, and no free text. Evaluation log: a hash of the input, plus the short quotes the reader used from answers that passed the checks above. |
| Imported results | Files with personal-detail keys are rejected (`diagnostic/importer.py`). |

The checks can't catch everything, for example a first name typed into a code comment or an interests box. That is
why the storage itself is locked down:

- **Bucket:** private (all public access blocked, ACLs off) and TLS only. A bucket-policy deny stops every principal
  except the app role from reading, writing, listing or deleting objects. Verified with the IAM policy simulator: the
  workshop admin role, which allows `*`, gets an explicit deny.
- **KMS key:** the key policy has no account-wide statement. Only the app role can encrypt or decrypt, and only through
  S3. The admin role can manage the key but not use it.
- **Versions:** overwritten or deleted objects are removed for good after 30 days (`NoncurrentVersionDays`).
- **This machine:** the server sets its umask to 077 and tightens `.codeai-data/` to the server's user (folders
  0700, files 0600).
- **Prompts:** Bedrock model-invocation logging is off in this account, so prompts that include student code aren't
  stored by AWS.

Account admins can still change these policies. That is true of any AWS account, and CloudTrail records it.

## Before a real classroom

- Run the server as its own role (an EC2 instance profile or ECS task role), set `AppRunnerRoleArn` to it, and keep
  people out of that role.
- Set a retention period with the school. Current objects are kept until deleted.
- Add a "delete this student" tool that removes every version under `progress/<id>/` and `workspace/<id>/`.
- The AI inspector (`--dev`) shows every student's prompts to anyone who can open the page. Keep it off.
- Teacher pages need `CODEAI_TEACHER_TOKEN`. Student pages rely on the 128-bit student id staying private.
