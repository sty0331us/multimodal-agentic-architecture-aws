# Security and Responsible AI

Controls deployed with **Multimodal Agentic Architecture on AWS**.

## Data protection

- S3 buckets: Block Public Access, SSL-only bucket policies, versioning, KMS CMK with rotation, access logging to a dedicated logs bucket.
- Uploaded images expire after 14 days.
- Presigned PUTs require `x-amz-server-side-encryption: aws:kms` and the stack CMK.
- Amazon Macie (optional, on by default) runs a daily classification job over documents + uploads buckets.
- CloudTrail records management events plus S3 data events on the two data buckets.

## Identity

Lambda roles are split:

- **Query function:** `bedrock:Converse`, `bedrock:Retrieve`, `bedrock:ApplyGuardrail`, Rekognition detect APIs, read/write uploads, read documents, KMS encrypt/decrypt.
- **Ingest function:** S3 read/write documents, `bedrock:StartIngestionJob`.
- **Knowledge Base role:** S3 read documents, `bedrock:InvokeModel` on the embedding model, `aoss:APIAccessAll` (further constrained by the AOSS data access policy principals list).

API methods except `/v1/health` require an API key bound to a usage plan. The long-running Function URL uses SigV4 (`AWS_IAM`).

WAF (REGIONAL) associates AWS Managed Common Rule Set with the API stage. `SizeRestrictions_BODY` is excluded so JSON queries are not blocked; prefer S3 object references over large base64 bodies.

## Bedrock Guardrails

The stack deploys `AWS::Bedrock::Guardrail` plus a numbered version. Filters:

- Content: HATE, INSULTS, SEXUAL, VIOLENCE, MISCONDUCT at HIGH; PROMPT_ATTACK on input
- PII anonymization: email, phone, name, address, SSN, PAN, AWS keys
- Denied topics: weapons/explosives and cyber attacks

The orchestrator passes:

```python
guardrailConfig={
  "guardrailIdentifier": os.environ["GUARDRAIL_IDENTIFIER"],
  "guardrailVersion": os.environ["GUARDRAIL_VERSION"],
  "trace": "enabled",
}
```

If `stopReason` is `guardrail_intervened`, the API returns a blocked-message rather than model output.

## Responsible AI operating rules

- Do not treat Rekognition face attributes as identity. The system prompt forbids naming private individuals from faces.
- RAG answers must include source URIs from `Retrieve`. If retrieval is empty, the model must say so.
- Human review of Macie findings and Guardrail traces should be part of the operating cadence.
- Disable model invocation logging in Bedrock if prompts may contain regulated data, or route logs to a restricted account.

## What this stack does not do

- No Amazon Cognito user pool (add one if you need per-user identity).
- No VPC isolation for Lambda (add VPC endpoints for S3, Bedrock, and AOSS if you require private networking).
- AOSS network policy uses `AllowFromPublic` with IAM data-plane auth — this is the Bedrock Knowledge Base documented pattern, not anonymous access.
