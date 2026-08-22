# Operations

## Deploy

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
npm install -g aws-cdk
cdk bootstrap
cdk deploy --context alarmEmail=you@example.com
eval "$(python scripts/export_outputs.py --stack MultimodalAgenticArchitectureStack --region us-east-1)"
```

Docker is required at deploy time because `PythonFunction` bundles `src/requirements.txt`.

## Bedrock model access

In the Bedrock console, enable:

- Anthropic Claude Sonnet 5 (`anthropic.claude-sonnet-5`) — reasoning tier
- Anthropic Claude 4.5 Haiku (`anthropic.claude-haiku-4-5-20251001-v1:0`) — fast tier
- Amazon Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`)

Geo inference profiles are supported: `us.anthropic.claude-sonnet-5`, `eu.anthropic.claude-sonnet-5`, `au.anthropic.claude-sonnet-5`, or `global.anthropic.claude-sonnet-5`. Set `bedrockModelId` / `BEDROCK_MODEL_ID` accordingly. Claude 4.5 Haiku geo profiles follow the same prefix pattern (`us.anthropic.claude-haiku-4-5-20251001-v1:0`, and so on).

Claude Sonnet 5 uses **adaptive thinking** by default. Lambda omits `temperature` while thinking is on (`THINKING_TYPE=adaptive`) and sets `output_config.effort` from `THINKING_EFFORT` (default `medium`). Raise `MAX_TOKENS` if answers truncate; thinking tokens count against the same budget. Claude 4.5 Haiku on the fast path uses temperature `0.2` and a smaller `FAST_TIER_MAX_TOKENS` budget; extended thinking is omitted to keep FAQ/chit-chat cheap.

## Ingestion

```bash
python scripts/ingest_document.py samples/documents/ppe_policy.md
```

Watch `StartIngestionJob` in CloudWatch logs on the ingest function. Query only after the job status is `COMPLETE`.

## Alarms

SNS topic `multimodal-agentic-architecture-aws-alarms` receives:

- Query/ingest Lambda errors
- API 5XX
- Query p99 duration > 50s
- Budget 80% actual and 100% forecasted (if enabled)

Confirm the email subscription after the first deploy.

## Cost controls

- AWS Budget named `multimodal-agentic-architecture-aws-monthly` (default $150)
- Cost Explorer: filter tag `Project=multimodal-agentic-architecture-aws`
- Toggle expensive account-level services via `cdk.json` context: `enableMacie`, `enableCloudTrail`, `enableBudgets`

OpenSearch Serverless minimum OCUs accrue even at idle. Destroy the stack when not in use (`cdk destroy`).

## Dashboards

CloudWatch dashboard **MultimodalAgenticArchitectureAws** graphs Lambda errors, duration, invocations, throttles, and API 5XX. Query and ingest logs land in `/aws/lambda/multimodal-agentic-query-handler` and `/aws/lambda/multimodal-agentic-ingest-handler`.

## Failure playbook

| Symptom | Likely cause | Action |
| --- | --- | --- |
| `ValidationException` on Converse | Model access not granted | Enable the model in Bedrock Model access |
| `access denied` on Retrieve | KB role / AOSS policy | Confirm KB role is in the AOSS data access policy |
| Index custom resource fails | Collection not ACTIVE yet | Re-deploy; the custom resource retries on update |
| Macie session already exists | Account already enabled Macie | Set `enableMacie=false` or import the session |
| API 403 | Missing `x-api-key` | `export API_KEY` from `scripts/export_outputs.py` |
| API 504 | Agent loop > 29s | Use `QueryFunctionUrl` with SigV4 |
