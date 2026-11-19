"""Infrastructure tests: synthesize the stack (no AWS account needed) and check the key rules."""

import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template
from calendly_infra.stack import GOLD_TABLES, CalendlyInsightsStack


@pytest.fixture(scope="module")
def template() -> Template:
    app = cdk.App()
    stack = CalendlyInsightsStack(app, "Test", alert_email="alerts@example.com")
    return Template.from_stack(stack)


def test_buckets_use_kms_and_block_public_access(template):
    template.resource_count_is("AWS::S3::Bucket", 2)
    template.all_resources_properties(
        "AWS::S3::Bucket",
        {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    Match.object_like({
                        "ServerSideEncryptionByDefault": Match.object_like(
                            {"SSEAlgorithm": "aws:kms"}
                        )
                    })
                ]
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        },
    )


def test_buckets_reject_non_https(template):
    policies = template.find_resources("AWS::S3::BucketPolicy")
    assert len(policies) == 2
    for policy in policies.values():
        statements = policy["Properties"]["PolicyDocument"]["Statement"]
        assert any(
            s["Effect"] == "Deny"
            and s["Condition"] == {"Bool": {"aws:SecureTransport": "false"}}
            for s in statements
        )


def test_key_rotation_and_encrypted_queue_secret_topic(template):
    template.has_resource_properties("AWS::KMS::Key", {"EnableKeyRotation": True})
    template.has_resource_properties("AWS::SQS::Queue", {"KmsMasterKeyId": Match.any_value()})
    template.has_resource_properties("AWS::SecretsManager::Secret", {"KmsKeyId": Match.any_value()})
    template.has_resource_properties("AWS::SNS::Topic", {"KmsMasterKeyId": Match.any_value()})


def test_lake_bucket_and_key_survive_destroy(template):
    lake = template.find_resources("AWS::S3::Bucket", {"DeletionPolicy": "Retain"})
    assert len(lake) == 1
    template.has_resource("AWS::KMS::Key", {"DeletionPolicy": "Retain"})


def test_webhook_route_is_post(template):
    template.has_resource_properties("AWS::ApiGatewayV2::Route", {"RouteKey": "POST /webhook"})


def test_schedule_is_daily_at_7_us_eastern(template):
    template.has_resource_properties(
        "AWS::Scheduler::Schedule",
        {
            "ScheduleExpression": "cron(0 7 * * ? *)",
            "ScheduleExpressionTimezone": "America/New_York",
        },
    )


def test_workflow_runs_steps_in_order_and_alerts_on_failure(template):
    machines = template.find_resources("AWS::StepFunctions::StateMachine")
    (machine,) = machines.values()
    definition = json.dumps(machine["Properties"]["DefinitionString"])
    order = ["ReplayRetryQueue", "CopySpendFiles", "RunSparkJob", "RegisterGoldTables"]
    positions = [definition.index(f'\\"{name}\\":{{') for name in order]
    assert positions == sorted(positions)
    assert "emr-serverless:startJobRun.sync" in definition
    assert "SendFailureAlert" in definition
    for table in GOLD_TABLES:
        assert table in definition


def test_alert_email_subscription(template):
    template.has_resource_properties(
        "AWS::SNS::Subscription", {"Protocol": "email", "Endpoint": "alerts@example.com"}
    )


def test_spark_executor_settings_are_consistent(template):
    """EMR rejects the job if the start/fixed executor count is above maxExecutors."""
    import re

    (machine,) = template.find_resources("AWS::StepFunctions::StateMachine").values()
    definition = json.dumps(machine["Properties"]["DefinitionString"])
    conf = dict(re.findall(r"--conf (spark\.[\w.]+)=(\w+)", definition))
    maximum = int(conf["spark.dynamicAllocation.maxExecutors"])
    assert int(conf["spark.dynamicAllocation.initialExecutors"]) <= maximum
    assert int(conf["spark.executor.instances"]) <= maximum
