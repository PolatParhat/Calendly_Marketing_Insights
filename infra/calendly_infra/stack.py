"""All AWS resources for the Calendly Marketing Insights pipeline, in one CDK stack.

Read it top to bottom in build order (docs/02_design/solution_design.md):
  Step 4  foundation      KMS key, encrypted S3 buckets, SNS alert topic
  Step 5  webhook         API Gateway + webhook Lambda + Secrets Manager + SQS retry queue
  Step 6  spend copy      Lambda that copies the spend files listed in file_index.json
  Step 7  processing      EMR Serverless application + job role + job code upload
  Step 9  warehouse       Glue database + Athena workgroup (tables are registered by the workflow)
  Step 8  orchestration   Step Functions daily workflow + EventBridge Scheduler + alarms

One stack keeps it simple: `cdk deploy` creates everything, `cdk destroy` removes it
(the data bucket and the KMS key are kept on destroy, so no booking data is ever lost by accident).
"""

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as apigw_integrations
from aws_cdk import aws_athena as athena
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_emrserverless as emrs
from aws_cdk import aws_glue as glue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from calendly_infra.job_package import REPO_ROOT, build_job_package

# EMR Serverless release: Spark 4.1.3 + Delta Lake 4.2.0, Python 3.11, Java 17 (same as local).
EMR_RELEASE = "emr-spark-8.2.0"
# Delta Lake ships with EMR; these settings put its jar files on Spark's class path.
DELTA_JARS = "/usr/share/aws/delta/lib/delta-spark.jar,/usr/share/aws/delta/lib/delta-storage.jar"

GLUE_DATABASE = "calendly_gold"
ATHENA_WORKGROUP = "calendly-insights"
GOLD_TABLES = [
    "daily_bookings_by_channel",
    "daily_spend_bookings_by_channel",
    "weekly_bookings_by_channel",
    "bookings_by_campaign",
    "bookings_by_time_slot",
    "weekly_meetings_by_host",
]
DAILY_SCHEDULE = "cron(0 7 * * ? *)"  # 07:00 every day, 1 hour after the spend file is published
SCHEDULE_TIMEZONE = "America/New_York"  # US Eastern, follows daylight saving automatically


class CalendlyInsightsStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, alert_email: str | None = None, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ------------------------------------------------------------------ Step 4: foundation
        # One customer-managed KMS (Key Management Service) key encrypts everything we store.
        key = kms.Key(
            self,
            "DataKey",
            alias="alias/calendly-insights",
            description="Encrypts the Calendly Insights lake, queue, secret and alerts",
            enable_key_rotation=True,  # AWS swaps the key material every year
            removal_policy=RemovalPolicy.RETAIN,
        )
        # CloudWatch alarms publish to the encrypted SNS topic, so they need to use the key.
        key.add_to_resource_policy(
            iam.PolicyStatement(
                principals=[iam.ServicePrincipal("cloudwatch.amazonaws.com")],
                actions=["kms:Decrypt", "kms:GenerateDataKey*"],
                resources=["*"],
            )
        )

        bucket_security = {
            "encryption": s3.BucketEncryption.KMS,  # SSE-KMS: server-side encryption with our key
            "encryption_key": key,
            "bucket_key_enabled": True,  # fewer KMS calls = lower cost
            "enforce_ssl": True,  # bucket policy rejects any request that is not HTTPS
            "block_public_access": s3.BlockPublicAccess.BLOCK_ALL,
        }
        # The lake: landing/ (raw files), bronze/, silver/, gold/ (Delta tables), plus logs.
        lake = s3.Bucket(
            self,
            "LakeBucket",
            **bucket_security,
            removal_policy=RemovalPolicy.RETAIN,  # booking data cannot be fetched again
            lifecycle_rules=[
                s3.LifecycleRule(prefix="athena-results/", expiration=Duration.days(30)),
                s3.LifecycleRule(prefix="emr-logs/", expiration=Duration.days(30)),
            ],
        )
        # Code for the EMR job; rebuilt from Git on every deploy, so safe to delete.
        artifacts = s3.Bucket(
            self,
            "ArtifactsBucket",
            **bucket_security,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        alerts = sns.Topic(
            self, "AlertTopic", display_name="Calendly Insights alerts", master_key=key
        )
        if alert_email:
            alerts.add_subscription(subscriptions.EmailSubscription(alert_email))
        alarm_action = cw_actions.SnsAction(alerts)

        # Lambda code: the whole lambdas/ folder (standard library + boto3 only, no packaging).
        lambda_code = lambda_.Code.from_asset(
            str(REPO_ROOT / "lambdas"), exclude=["__pycache__", "*.pyc"]
        )

        def python_lambda(name: str, handler: str, timeout: Duration, env: dict) -> lambda_.Function:
            return lambda_.Function(
                self,
                name,
                runtime=lambda_.Runtime.PYTHON_3_11,
                architecture=lambda_.Architecture.ARM_64,  # Graviton: cheaper, same Python code
                handler=handler,
                code=lambda_code,
                timeout=timeout,
                memory_size=256,
                environment=env,
                log_group=logs.LogGroup(
                    self,
                    f"{name}Logs",
                    retention=logs.RetentionDays.ONE_MONTH,
                    removal_policy=RemovalPolicy.DESTROY,
                ),
            )

        # ------------------------------------------------------------------ Step 5: webhook
        signing_key = secretsmanager.Secret(
            self,
            "WebhookSigningKey",
            description="Calendly webhook signing key (replace with the SME's key after deploy)",
            encryption_key=key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True, password_length=40
            ),
        )
        retry_queue = sqs.Queue(
            self,
            "WebhookRetryQueue",
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=key,
            retention_period=Duration.days(14),  # the maximum SQS allows
            enforce_ssl=True,
        )
        webhook_fn = python_lambda(
            "WebhookFunction",
            "webhook.handler",
            Duration.seconds(10),
            {
                "LAKE_BUCKET": lake.bucket_name,
                "RETRY_QUEUE_URL": retry_queue.queue_url,
                "SIGNING_KEY_SECRET_ARN": signing_key.secret_arn,
            },
        )
        lake.grant_put(webhook_fn, "landing/calendly/*")  # write-only, one folder
        retry_queue.grant_send_messages(webhook_fn)
        signing_key.grant_read(webhook_fn)

        api = apigw.HttpApi(
            self, "WebhookApi", description="Receives Calendly invitee.created webhooks"
        )
        api.add_routes(
            path="/webhook",
            methods=[apigw.HttpMethod.POST],
            integration=apigw_integrations.HttpLambdaIntegration("WebhookIntegration", webhook_fn),
        )
        # Throttling and access logs on the default stage (escape hatch to the CloudFormation level).
        api_logs = logs.LogGroup(
            self,
            "WebhookApiAccessLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        stage = api.default_stage.node.default_child
        stage.default_route_settings = apigw.CfnStage.RouteSettingsProperty(
            throttling_burst_limit=50, throttling_rate_limit=20
        )
        stage.access_log_settings = apigw.CfnStage.AccessLogSettingsProperty(
            destination_arn=api_logs.log_group_arn,
            format=(
                '{"requestId":"$context.requestId","time":"$context.requestTime",'
                '"status":"$context.status","ip":"$context.identity.sourceIp",'
                '"latencyMs":"$context.responseLatency"}'
            ),
        )

        webhook_fn.metric_errors(period=Duration.minutes(5)).create_alarm(
            self,
            "WebhookErrorsAlarm",
            alarm_description="The webhook Lambda failed (Calendly delivery may not be stored)",
            threshold=1,
            evaluation_periods=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        ).add_alarm_action(alarm_action)
        retry_queue.metric_approximate_number_of_messages_visible(
            period=Duration.minutes(5)
        ).create_alarm(
            self,
            "RetryQueueNotEmptyAlarm",
            alarm_description="Webhook events are waiting in the retry queue (S3 write failed)",
            threshold=1,
            evaluation_periods=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        ).add_alarm_action(alarm_action)

        replay_fn = python_lambda(
            "RetryReplayFunction",
            "retry_replay.handler",
            Duration.minutes(5),
            {"LAKE_BUCKET": lake.bucket_name, "RETRY_QUEUE_URL": retry_queue.queue_url},
        )
        lake.grant_put(replay_fn, "landing/calendly/*")
        retry_queue.grant_consume_messages(replay_fn)

        # ------------------------------------------------------------------ Step 6: spend copy
        spend_fn = python_lambda(
            "SpendCopyFunction",
            "spend_copy.handler",
            Duration.minutes(3),
            {
                "LAKE_BUCKET": lake.bucket_name,
                "SPEND_BASE_URL": (
                    "https://dea-data-bucket.s3.us-east-1.amazonaws.com/calendly_spend_data"
                ),
            },
        )
        # Read is needed to check which files are already there (HeadObject + ListBucket).
        lake.grant_read(spend_fn, "landing/spend/*")
        lake.grant_put(spend_fn, "landing/spend/*")

        # ------------------------------------------------------------------ Step 7: processing
        job_dir = build_job_package(Path(__file__).resolve().parents[1] / "build" / "emr_job")
        job_code = s3deploy.BucketDeployment(
            self,
            "JobCode",
            sources=[s3deploy.Source.asset(str(job_dir))],
            destination_bucket=artifacts,
            destination_key_prefix="emr/",
        )

        emr_app = emrs.CfnApplication(
            self,
            "SparkApplication",
            name="calendly-insights",
            release_label=EMR_RELEASE,
            type="SPARK",
            architecture="ARM64",
            auto_start_configuration=emrs.CfnApplication.AutoStartConfigurationProperty(
                enabled=True
            ),
            auto_stop_configuration=emrs.CfnApplication.AutoStopConfigurationProperty(
                enabled=True, idle_timeout_minutes=5  # no cost while idle
            ),
            maximum_capacity=emrs.CfnApplication.MaximumAllowedResourcesProperty(
                cpu="8 vCPU", memory="32 GB"  # cost guard: the job needs far less
            ),
        )

        job_role = iam.Role(
            self,
            "SparkJobRole",
            assumed_by=iam.ServicePrincipal("emr-serverless.amazonaws.com"),
            description="What the Spark job may do: read/write the lake, read its code",
        )
        lake.grant_read_write(job_role)
        artifacts.grant_read(job_role)

        spark_submit_parameters = " ".join(
            [
                f"--conf spark.submit.pyFiles=s3://{artifacts.bucket_name}/emr/calendly_insights.zip",
                f"--conf spark.jars={DELTA_JARS}",
                "--conf spark.driver.cores=1 --conf spark.driver.memory=2g",
                "--conf spark.executor.cores=1 --conf spark.executor.memory=2g",
                # EMR Serverless starts with 3 executors by default; that must not exceed
                # maxExecutors, so set the start value too (first run failed without it).
                "--conf spark.executor.instances=1",
                "--conf spark.dynamicAllocation.initialExecutors=1",
                "--conf spark.dynamicAllocation.maxExecutors=2",
            ]
        )

        # ------------------------------------------------------------------ Step 9: warehouse
        glue_db = glue.CfnDatabase(
            self,
            "GoldDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=GLUE_DATABASE, description="Gold Delta tables of Calendly Insights"
            ),
        )
        workgroup = athena.CfnWorkGroup(
            self,
            "AthenaWorkgroup",
            name=ATHENA_WORKGROUP,
            recursive_delete_option=True,
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                enforce_work_group_configuration=True,
                engine_version=athena.CfnWorkGroup.EngineVersionProperty(
                    selected_engine_version="Athena engine version 3"
                ),
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{lake.bucket_name}/athena-results/",
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_KMS", kms_key=key.key_arn
                    ),
                ),
            ),
        )

        # ------------------------------------------------------------------ Step 8: orchestration
        retry = {"errors": ["States.ALL"], "max_attempts": 2, "backoff_rate": 2.0}

        replay_step = tasks.LambdaInvoke(
            self,
            "ReplayRetryQueue",
            lambda_function=replay_fn,
            payload_response_only=True,
            result_path="$.replay",
        )
        replay_step.add_retry(interval=Duration.seconds(30), **retry)

        spend_step = tasks.LambdaInvoke(
            self,
            "CopySpendFiles",
            lambda_function=spend_fn,
            payload_response_only=True,
            result_path="$.spend",
        )
        spend_step.add_retry(interval=Duration.minutes(2), **retry)

        # Step Functions has no ready-made CDK task for EMR Serverless, so write the state directly.
        # ".sync" = wait until the Spark job has finished (and fail if the job fails).
        spark_step = sfn.CustomState(
            self,
            "RunSparkJob",
            state_json={
                "Type": "Task",
                "Resource": "arn:aws:states:::emr-serverless:startJobRun.sync",
                "Parameters": {
                    "ApplicationId": emr_app.attr_application_id,
                    "ExecutionRoleArn": job_role.role_arn,
                    "Name": "calendly-insights-daily",
                    "JobDriver": {
                        "SparkSubmit": {
                            "EntryPoint": f"s3://{artifacts.bucket_name}/emr/run_pipeline.py",
                            "EntryPointArguments": [
                                "--landing",
                                f"s3://{lake.bucket_name}/landing",
                                "--lake",
                                f"s3://{lake.bucket_name}",
                                "--cloud",
                            ],
                            "SparkSubmitParameters": spark_submit_parameters,
                        }
                    },
                    "ConfigurationOverrides": {
                        "MonitoringConfiguration": {
                            "S3MonitoringConfiguration": {
                                "LogUri": f"s3://{lake.bucket_name}/emr-logs/",
                                "EncryptionKeyArn": key.key_arn,
                            }
                        }
                    },
                },
                "ResultPath": "$.spark",
                "Retry": [
                    {
                        "ErrorEquals": ["States.ALL"],
                        "IntervalSeconds": 60,
                        "MaxAttempts": 2,
                        "BackoffRate": 2,
                    }
                ],
            },
        )

        # Register each Gold Delta table in the Glue catalog so Athena can query it by name.
        # "IF NOT EXISTS" makes this safe to run every day; Athena reads the schema from Delta.
        register_ddl = [
            f"CREATE EXTERNAL TABLE IF NOT EXISTS {GLUE_DATABASE}.{table} "
            f"LOCATION 's3://{lake.bucket_name}/gold/{table}/' "
            "TBLPROPERTIES ('table_type'='DELTA')"
            for table in GOLD_TABLES
        ]
        list_tables = sfn.Pass(
            self,
            "ListGoldTables",
            result=sfn.Result.from_array(register_ddl),
            result_path="$.registerDdl",
        )
        register_one = tasks.AthenaStartQueryExecution(
            self,
            "RegisterGoldTable",
            query_string=sfn.JsonPath.string_at("$"),
            work_group=ATHENA_WORKGROUP,
            query_execution_context=tasks.QueryExecutionContext(
                catalog_name="AwsDataCatalog", database_name=GLUE_DATABASE
            ),
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,  # wait for the query to finish
        )
        register_one.add_retry(interval=Duration.seconds(10), **retry)
        register_tables = sfn.Map(
            self,
            "RegisterGoldTables",
            items_path="$.registerDdl",
            max_concurrency=1,
            result_path=sfn.JsonPath.DISCARD,
        ).item_processor(register_one)

        daily_run = sfn.Parallel(self, "DailyRun", result_path=sfn.JsonPath.DISCARD).branch(
            replay_step.next(spend_step).next(spark_step).next(list_tables).next(register_tables)
        )
        send_alert = tasks.SnsPublish(
            self,
            "SendFailureAlert",
            topic=alerts,
            subject="Calendly Insights: daily run failed",
            message=sfn.TaskInput.from_text(
                sfn.JsonPath.format(
                    "The daily pipeline run failed after retries. Error: {} Cause: {}",
                    sfn.JsonPath.string_at("$.error.Error"),
                    sfn.JsonPath.string_at("$.error.Cause"),
                )
            ),
            result_path=sfn.JsonPath.DISCARD,
        )
        daily_run.add_catch(
            send_alert.next(sfn.Fail(self, "RunFailed")), errors=["States.ALL"], result_path="$.error"
        )

        workflow = sfn.StateMachine(
            self,
            "DailyWorkflow",
            definition_body=sfn.DefinitionBody.from_chainable(
                daily_run.next(sfn.Succeed(self, "RunSucceeded"))
            ),
            timeout=Duration.hours(2),
            logs=sfn.LogOptions(
                destination=logs.LogGroup(
                    self,
                    "DailyWorkflowLogs",
                    retention=logs.RetentionDays.ONE_MONTH,
                    removal_policy=RemovalPolicy.DESTROY,
                ),
                level=sfn.LogLevel.ERROR,
            ),
        )
        workflow.node.add_dependency(job_code)  # job code is uploaded before the workflow exists

        # Permissions the workflow needs for EMR Serverless and Athena (the Lambda and SNS
        # permissions are added by CDK automatically).
        app_arn = emr_app.attr_arn
        workflow.add_to_role_policy(
            iam.PolicyStatement(actions=["emr-serverless:StartJobRun"], resources=[app_arn])
        )
        workflow.add_to_role_policy(
            iam.PolicyStatement(
                actions=["emr-serverless:GetJobRun", "emr-serverless:CancelJobRun"],
                resources=[f"{app_arn}/jobruns/*"],
            )
        )
        workflow.add_to_role_policy(
            iam.PolicyStatement(actions=["iam:PassRole"], resources=[job_role.role_arn])
        )
        workflow.add_to_role_policy(  # the ".sync" pattern listens for job events via EventBridge
            iam.PolicyStatement(
                actions=["events:PutTargets", "events:PutRule", "events:DescribeRule"],
                resources=[
                    (f"arn:aws:events:{self.region}:{self.account}:rule/"
                    "StepFunctionsGetEventsForEMRServerlessJobRule")
                ],
            )
        )
        workflow.add_to_role_policy(
            iam.PolicyStatement(
                actions=["glue:GetDatabase", "glue:GetTable", "glue:CreateTable"],
                resources=[
                    f"arn:aws:glue:{self.region}:{self.account}:catalog",
                    f"arn:aws:glue:{self.region}:{self.account}:database/{GLUE_DATABASE}",
                    f"arn:aws:glue:{self.region}:{self.account}:table/{GLUE_DATABASE}/*",
                ],
            )
        )
        lake.grant_read(workflow, "gold/*")  # Athena reads the Delta log to learn the schema
        lake.grant_read_write(workflow, "athena-results/*")
        workflow.node.add_dependency(glue_db, workgroup)

        workflow.metric_timed_out(period=Duration.minutes(5)).create_alarm(
            self,
            "WorkflowTimedOutAlarm",
            alarm_description="The daily workflow ran longer than 2 hours",
            threshold=1,
            evaluation_periods=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        ).add_alarm_action(alarm_action)

        # EventBridge Scheduler starts the workflow every day at 07:00 US Eastern.
        scheduler_role = iam.Role(
            self, "SchedulerRole", assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com")
        )
        workflow.grant_start_execution(scheduler_role)
        scheduler.CfnSchedule(
            self,
            "DailySchedule",
            description="Start the Calendly Insights daily workflow",
            schedule_expression=DAILY_SCHEDULE,
            schedule_expression_timezone=SCHEDULE_TIMEZONE,
            flexible_time_window=scheduler.CfnSchedule.FlexibleTimeWindowProperty(mode="OFF"),
            target=scheduler.CfnSchedule.TargetProperty(
                arn=workflow.state_machine_arn,
                role_arn=scheduler_role.role_arn,
                input="{}",
                retry_policy=scheduler.CfnSchedule.RetryPolicyProperty(maximum_retry_attempts=3),
            ),
        )

        # ------------------------------------------------------------------ outputs
        # Printed after `cdk deploy`; the commands in docs/03_deploy/runbook.md use them.
        outputs = {
            "WebhookUrl": f"{api.api_endpoint}/webhook",
            "LakeBucketName": lake.bucket_name,
            "SigningKeySecretArn": signing_key.secret_arn,
            "RetryQueueUrl": retry_queue.queue_url,
            "SpendCopyFunctionName": spend_fn.function_name,
            "StateMachineArn": workflow.state_machine_arn,
            "EmrApplicationId": emr_app.attr_application_id,
            "AthenaWorkgroupName": ATHENA_WORKGROUP,
            "GlueDatabaseName": GLUE_DATABASE,
            "AlertTopicArn": alerts.topic_arn,
        }
        for name, value in outputs.items():
            CfnOutput(self, name, value=value)
