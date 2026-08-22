"""Least-privilege IAM roles and Lambda functions for query + ingest."""

from __future__ import annotations

from aws_cdk import Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk.aws_lambda_python_alpha import PythonFunction

from constructs import Construct


class Compute(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        key: kms.IKey,
        documents_bucket: s3.IBucket,
        uploads_bucket: s3.IBucket,
        knowledge_base_id: str,
        data_source_id: str,
        guardrail_id: str,
        guardrail_version: str,
        bedrock_model_id: str,
        fast_tier_model_id: str,
        router_mode: str,
        log_retention: logs.RetentionDays,
    ) -> None:
        super().__init__(scope, construct_id)
        region = Stack.of(self).region
        account = Stack.of(self).account

        common_env = {
            "POWERTOOLS_SERVICE_NAME": "multimodal-agentic-architecture-aws",
            "POWERTOOLS_METRICS_NAMESPACE": "MultimodalAgenticArchitectureAws",
            "LOG_LEVEL": "INFO",
            "AWS_REGION": region,
            "BEDROCK_MODEL_ID": bedrock_model_id,
            "REASONING_TIER_MODEL_ID": bedrock_model_id,
            "FAST_TIER_MODEL_ID": fast_tier_model_id,
            "ROUTER_MODE": router_mode,
            "ROUTER_ESCALATE_ON_TOOLS": "true",
            "FAST_TIER_MAX_TOKENS": "1024",
            "KNOWLEDGE_BASE_ID": knowledge_base_id,
            "DATA_SOURCE_ID": data_source_id,
            "GUARDRAIL_IDENTIFIER": guardrail_id,
            "GUARDRAIL_VERSION": guardrail_version,
            "DOCUMENTS_BUCKET": documents_bucket.bucket_name,
            "UPLOADS_BUCKET": uploads_bucket.bucket_name,
            "DOCUMENTS_PREFIX": "knowledge/",
            "KMS_KEY_ID": key.key_arn,
            "MAX_TOOL_ITERATIONS": "6",
            "MAX_TOKENS": "8192",
            "THINKING_TYPE": "adaptive",
            "THINKING_EFFORT": "medium",
        }

        query_log_group = logs.LogGroup(
            self,
            "QueryLogGroup",
            log_group_name="/aws/lambda/multimodal-agentic-query-handler",
            retention=log_retention,
        )
        ingest_log_group = logs.LogGroup(
            self,
            "IngestLogGroup",
            log_group_name="/aws/lambda/multimodal-agentic-ingest-handler",
            retention=log_retention,
        )
        self.query_fn = PythonFunction(
            self,
            "QueryFunction",
            function_name="multimodal-agentic-query-handler",
            entry="src",
            runtime=lambda_.Runtime.PYTHON_3_12,
            index="handlers/query_handler.py",
            handler="lambda_handler",
            timeout=Duration.minutes(2),
            memory_size=1024,
            tracing=lambda_.Tracing.ACTIVE,
            environment=common_env,
            reserved_concurrent_executions=20,
            log_group=query_log_group,
            description="Query handler for Multimodal Agentic Architecture on AWS",
        )
        self.ingest_fn = PythonFunction(
            self,
            "IngestFunction",
            function_name="multimodal-agentic-ingest-handler",
            entry="src",
            runtime=lambda_.Runtime.PYTHON_3_12,
            index="handlers/ingest_handler.py",
            handler="lambda_handler",
            timeout=Duration.minutes(1),
            memory_size=512,
            tracing=lambda_.Tracing.ACTIVE,
            environment=common_env,
            reserved_concurrent_executions=5,
            log_group=ingest_log_group,
            description="Ingest handler for Multimodal Agentic Architecture on AWS",
        )

        key.grant_encrypt_decrypt(self.query_fn)
        key.grant_encrypt_decrypt(self.ingest_fn)
        uploads_bucket.grant_read_write(self.query_fn)
        documents_bucket.grant_read(self.query_fn)
        documents_bucket.grant_read_write(self.ingest_fn)
        uploads_bucket.grant_read(self.ingest_fn)

        self.query_fn.add_to_role_policy(
            iam.PolicyStatement(
                sid="BedrockConverseAndRetrieve",
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                    "bedrock:ConverseStream",
                    "bedrock:ApplyGuardrail",
                    "bedrock:Retrieve",
                    "bedrock:RetrieveAndGenerate",
                ],
                resources=["*"],
            )
        )
        self.query_fn.add_to_role_policy(
            iam.PolicyStatement(
                sid="RekognitionVision",
                actions=[
                    "rekognition:DetectLabels",
                    "rekognition:DetectText",
                    "rekognition:DetectFaces",
                    "rekognition:DetectModerationLabels",
                ],
                resources=["*"],
            )
        )
        self.ingest_fn.add_to_role_policy(
            iam.PolicyStatement(
                sid="StartKbIngestion",
                actions=["bedrock:StartIngestionJob", "bedrock:GetIngestionJob"],
                resources=[
                    f"arn:aws:bedrock:{region}:{account}:knowledge-base/*",
                ],
            )
        )


def knowledge_base_role(
    scope: Construct, construct_id: str, *, documents_bucket: s3.IBucket, embedding_model_id: str
) -> iam.Role:
    region = Stack.of(scope).region
    role = iam.Role(
        scope,
        construct_id,
        assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
        description="Bedrock Knowledge Base execution role (S3 + AOSS + embeddings)",
    )
    documents_bucket.grant_read(role)
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[f"arn:aws:bedrock:{region}::foundation-model/{embedding_model_id}"],
        )
    )
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["aoss:APIAccessAll"],
            resources=["*"],
        )
    )
    return role
