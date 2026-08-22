# Architecture

This document expands on the README with component contracts, failure modes, and scaling notes for **Multimodal Agentic Architecture on AWS**.

## Control flow

1. Client obtains an API key (Usage Plan) and optionally a presigned PUT URL.
2. Images should land in the **uploads** bucket (KMS-encrypted, 14-day expiry). Documents land in the **documents** bucket under `knowledge/`.
3. `POST /v1/query` invokes the query Lambda. The handler validates the payload, the **model router** picks Claude 4.5 Haiku vs Sonnet 5, then the agent loop runs.
4. Each Bedrock `converse` call is wrapped with `guardrailConfig.guardrailIdentifier` and `guardrailConfig.guardrailVersion` on **both** tiers.
5. Tool use:
   - `analyze_image` → Rekognition `DetectLabels` / `DetectText` / `DetectFaces` / `DetectModerationLabels`
   - `retrieve_knowledge` → Bedrock Agent Runtime `Retrieve` against the Knowledge Base
6. Document `ObjectCreated` on `knowledge/*` starts a Knowledge Base ingestion job (conflicts are swallowed if a job is already running).

## Why Rekognition *and* Bedrock vision

Claude Sonnet 5 inspects pixels directly via the Converse `image` content block (image is placed before the text prompt). Rekognition adds:

- Deterministic labels and OCR with confidence scores
- Moderation labels that are easier to audit than model prose
- Face *counts* without performing identification (the prompt forbids naming private individuals)

The agent is instructed to combine both signals and to ground policy answers in Knowledge Base passages.

## Dual-tier cascading

`src/agent/router.py` scores complexity with zero-cost heuristics (and optional Claude 4.5 Haiku JSON classification when `ROUTER_MODE=hybrid` and confidence is below `ROUTER_CONFIDENCE_FLOOR`). Fast-tier answers can escalate mid-loop to Sonnet 5. See the README cascading section for metrics and env vars.

## API Gateway 29-second limit

REST APIs cap Lambda integration at 29 seconds. Multimodal tool loops can exceed that. The stack therefore also creates a **Lambda Function URL** (`QueryFunctionUrl` output) with IAM auth and the function timeout set to 2 minutes. Use the Function URL (or an async job pattern) for heavy vision + RAG turns; keep API Gateway for health, presign, ingest, and short queries.

## OpenSearch Serverless index

Bedrock Knowledge Bases require a k-NN index *before* `AWS::Bedrock::KnowledgeBase` is created. A custom resource Lambda signs requests to the collection endpoint (`aoss` SigV4) and PUTs the Titan v2 1024-dimension mapping.

## Scaling

| Resource | Default | Notes |
| --- | --- | --- |
| Query Lambda reserved concurrency | 20 | Protects Bedrock from burst-driven throttling |
| Ingest Lambda reserved concurrency | 5 | Ingestion jobs are account-limited |
| API throttle | 10 rps / 20 burst | Usage plan |
| Budget | $150/month | Override `monthlyBudgetUsd` |

Increase reserved concurrency only after you have Bedrock provisioned throughput or have validated on-demand quotas.
