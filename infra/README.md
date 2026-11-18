# infra/

AWS infrastructure as code, written with **AWS CDK in Python**. Filled in from Step 4.

Planned stacks (see `docs/02_design/solution_design.md`):
- Foundation: KMS key, encrypted S3 bucket (landing/bronze/silver/gold), IAM roles, SNS alert topic
- Webhook: API Gateway HTTP API, webhook Lambda, Secrets Manager signing key, SQS retry queue
- Spend ingestion Lambda
- EMR Serverless application for the PySpark job
- EventBridge Scheduler + Step Functions daily workflow
- Glue Data Catalog database for Athena

Rule: the developer runs every `cdk deploy` / `cdk destroy` by hand; CI only runs `cdk synth`.
