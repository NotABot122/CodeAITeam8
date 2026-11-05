# AWS storage setup (prototype)

## What exists

The standards loader can optionally read one pinned version of the CSTA JSON standards file from S3. It loads the checked-in JSON by default for offline development. The JSON was exported from the existing workbook; the workbook is retained as an import/reference source. Lessons, questions, rubrics and project manifests remain checked-in files: moving the workbook does not make those objects dynamically sourced from S3. The pathway chooser uses relevant workbook standards, but its generated or selected material is not automatically verified against the workbook.

The app currently saves progress, profiles, diagnostic state, workspaces, themes and event logs on local disk. The included CloudFormation template creates a private S3 bucket and a DynamoDB table, but **the application does not yet read or write student data in DynamoDB**. Do not use the table as if student-data migration were complete. Runtime authentication and school-specific data controls must be designed before production use.

## Create infrastructure

In the team's AWS account, choose a region, an owner for the resources and a budget. Install AWS CLI v2 and boto3, configure AWS IAM Identity Center or an execution role, and confirm the active account with `aws sts get-caller-identity`. Deploy after reviewing the template:

```sh
aws cloudformation deploy --stack-name codeai-storage --template-file infrastructure/curriculum-and-progress.yaml --region "$AWS_REGION"
aws cloudformation describe-stacks --stack-name codeai-storage --region "$AWS_REGION" --query 'Stacks[0].Outputs'
```

The bucket has versioning, encryption, blocked public access and a TLS-only policy. The on-demand table has encryption and point-in-time recovery. Both are retained if the stack is deleted. These resources and recovery incur AWS charges. The template creates no IAM identities and grants no app access.

Review the JSON standards and upload the approved file with a curriculum publisher role. Record the returned VersionId in deployment configuration (use a consistent region):

```sh
aws s3api put-object --bucket "$CURRICULUM_BUCKET" --key standards/csta.json --body 'documentation/curriculum/csta-standards.json' --region "$AWS_REGION" --query VersionId --output text
export CODEAI_CURRICULUM="s3://$CURRICULUM_BUCKET/standards/csta.json"
export CODEAI_CURRICULUM_VERSION_ID="<the returned VersionId>"
export CODEAI_AWS_REGION="$AWS_REGION"
```

The application role needs `s3:GetObjectVersion` scoped to this object; the publisher needs separate write access. Use IAM roles and temporary credentials, not keys in source control. `CODEAI_CURRICULUM` and its version are server configuration, not student-provided inputs. Invalid or unavailable S3 data raises CurriculumError; the pathway caller currently proceeds without standards, so an S3 outage does not guarantee curriculum-grounded decisions. Add an explicit teacher-visible status and release policy before classroom deployment.

## Proposed student data model (not wired)

Use the table as a starting point for a migration with partition key `PK = STUDENT#<opaque-id>` and sort keys such as `PROFILE`, `LEVEL#<project>#<level>`, and `DIAGNOSTIC#<id>`. Record course/version, student level, stage evidence, attempts, hint count, last activity and route decisions; do not infer mastery from an ungraded result. Store larger code artifacts separately with access-controlled references. Design cohort and teacher queries explicitly rather than scanning all student items; include school/section authorization and a retention policy. Add conditional writes to prevent lost concurrent updates and define migration, recovery, deletion, and data minimization before wiring the API. Existing local diagnostics, logs and workspaces must be included in the migration or explicitly kept on persistent storage.

Retention rates require a defined cohort and time window; start with aggregate reporting rather than treating a rate as a student's mastery. Do not deploy student information until access controls, school policy and recovery are reviewed.
