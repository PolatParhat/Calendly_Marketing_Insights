#!/usr/bin/env bash
# Open every tab for the final walkthrough video, in the order of docs/07_walkthrough/speaker_notes.md.
# Reads names and IDs from the deployed stack, so nothing account-specific is stored in Git.
#   bash scripts/open_recording_tabs.sh            open the tabs (macOS `open`)
#   DRY_RUN=1 bash scripts/open_recording_tabs.sh  only print the URLs
# Start the dashboard first (tab 12):  AWS_REGION=us-west-1 streamlit run dashboard/app.py
set -euo pipefail

STACK=CalendlyInsights
REGION=${AWS_REGION:-$(aws configure get region)}
REPO=https://github.com/PolatParhat/Calendly_Marketing_Insights
CONSOLE="https://${REGION}.console.aws.amazon.com"

out() { aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
urlencode() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"; }

LAKE=$(out LakeBucketName)
SM=$(out StateMachineArn)
API_ID=$(out WebhookUrl | sed -E 's#https://([^.]+)\..*#\1#')
STACK_ID=$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].StackId" --output text)

TABS=(
  "$REPO"                                                                                   # 1 README
  "$REPO/blob/main/docs/02_design/architecture.png"                                         # 2 architecture
  "$CONSOLE/cloudformation/home?region=$REGION#/stacks/resources?stackId=$(urlencode "$STACK_ID")" # 3
  "$CONSOLE/apigateway/main/develop/routes?api=$API_ID&region=$REGION"                      # 4 API routes
  "$CONSOLE/lambda/home?region=$REGION#/functions?fo=and&o0=%3A&v0=CalendlyInsights"        # 5 Lambdas
  "$CONSOLE/s3/buckets/$LAKE?region=$REGION&tab=objects"                                    # 6 lake bucket
  "$CONSOLE/scheduler/home?region=$REGION#schedules"                                        # 7 schedule
  "$CONSOLE/states/home?region=$REGION#/statemachines/view/$(urlencode "$SM")"              # 8 workflow
  "$CONSOLE/emr/home?region=$REGION#/serverless"                                            # 9 EMR Serverless
  "$CONSOLE/athena/home?region=$REGION#/query-editor"                                       # 10 Athena
  "http://localhost:8501"                                                                   # 12 dashboard
  "$CONSOLE/kms/home?region=$REGION#/kms/keys"                                              # 13 KMS
  "https://us-east-1.console.aws.amazon.com/iam/home#/roles?search=CalendlyInsights"        # 14 IAM roles
  "$REPO/actions"                                                                           # 15 CI
  "$REPO/tree/main/src/calendly_insights"                                                   # 16 code
  "$REPO/blob/main/docs/decisions.md"                                                       # 17 decisions
)
# Tab 11 (the alert email) is in your mail app: open it yourself and hide the sender/recipient lines.

for url in "${TABS[@]}"; do
  if [[ -n "${DRY_RUN:-}" ]]; then echo "$url"; else open "$url"; sleep 0.5; fi
done
