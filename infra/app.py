"""CDK app entry point: `cdk synth` / `cdk deploy` run this file (see cdk.json).

Optional context values (pass with -c on the command line):
  alert_email=<address>   subscribe this email to the failure alerts (SNS topic)
"""

import os

import aws_cdk as cdk
from calendly_infra.stack import CalendlyInsightsStack

app = cdk.App()
CalendlyInsightsStack(
    app,
    "CalendlyInsights",
    alert_email=app.node.try_get_context("alert_email"),
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),  # filled in by the cdk CLI from your AWS profile
        region=os.getenv("CDK_DEFAULT_REGION"),
    ),
)
app.synth()
