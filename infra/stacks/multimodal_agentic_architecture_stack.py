"""Root CDK stack for Multimodal Agentic Architecture on AWS."""

from __future__ import annotations

from aws_cdk import CfnOutput, Stack, Tags
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as s3n

from constructs import Construct
from infra.constructs.api import AgentApi
from infra.constructs.compute import Compute, knowledge_base_role
from infra.constructs.context import ctx, ctx_bool
from infra.constructs.governance import Governance
from infra.constructs.knowledge_base import KnowledgeBase, build_guardrail
from infra.constructs.macie import SensitiveDataScan
from infra.constructs.observability import Observability
from infra.constructs.opensearch import VectorStore
from infra.constructs.storage import Storage


class MultimodalAgenticArchitectureStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project = str(ctx(self, "projectName", "multimodal-agentic-architecture-aws"))
        model_id = str(ctx(self, "bedrockModelId", "anthropic.claude-sonnet-5"))
        fast_tier_model_id = str(
            ctx(self, "fastTierModelId", "anthropic.claude-haiku-4-5-20251001-v1:0")
        )
        router_mode = str(ctx(self, "routerMode", "hybrid"))
        embedding_id = str(ctx(self, "embeddingModelId", "amazon.titan-embed-text-v2:0"))
        embedding_dims = int(ctx(self, "embeddingDimensions", 1024))
        alarm_email = str(ctx(self, "alarmEmail", ""))
        budget_usd = int(ctx(self, "monthlyBudgetUsd", 150))
        retention_days = int(ctx(self, "logRetentionDays", 30))
        retention_map = {
            1: logs.RetentionDays.ONE_DAY,
            3: logs.RetentionDays.THREE_DAYS,
            7: logs.RetentionDays.ONE_WEEK,
            14: logs.RetentionDays.TWO_WEEKS,
            30: logs.RetentionDays.ONE_MONTH,
            90: logs.RetentionDays.THREE_MONTHS,
        }
        retention = retention_map.get(retention_days, logs.RetentionDays.ONE_MONTH)
        collection_name = f"maaaws-{self.node.addr[-8:].lower()}"

        Tags.of(self).add("Project", project)
        Tags.of(self).add("Application", "Multimodal Agentic Architecture on AWS")
        Tags.of(self).add("Stack", construct_id)
        Tags.of(self).add("ManagedBy", "cdk")

        storage = Storage(self, "Storage", project_name=project)
        kb_role = knowledge_base_role(
            self,
            "KnowledgeBaseRole",
            documents_bucket=storage.documents_bucket,
            embedding_model_id=embedding_id,
        )
        vector_store = VectorStore(
            self,
            "VectorStore",
            collection_name=collection_name,
            embedding_dimensions=embedding_dims,
            knowledge_base_role=kb_role,
        )
        knowledge = KnowledgeBase(
            self,
            "Knowledge",
            documents_bucket=storage.documents_bucket,
            vector_store=vector_store,
            knowledge_base_role=kb_role,
            embedding_model_id=embedding_id,
        )
        guardrail = build_guardrail(self, "Guardrail")
        guardrail_version = bedrock.CfnGuardrailVersion(
            self,
            "GuardrailVersion",
            guardrail_identifier=guardrail.attr_guardrail_id,
            description="Production version for Converse API",
        )

        compute = Compute(
            self,
            "Compute",
            key=storage.key,
            documents_bucket=storage.documents_bucket,
            uploads_bucket=storage.uploads_bucket,
            knowledge_base_id=knowledge.knowledge_base_id,
            data_source_id=knowledge.data_source_id,
            guardrail_id=guardrail.attr_guardrail_id,
            guardrail_version=guardrail_version.attr_version,
            bedrock_model_id=model_id,
            fast_tier_model_id=fast_tier_model_id,
            router_mode=router_mode,
            log_retention=retention,
        )
        query_url = compute.query_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.AWS_IAM,
            cors=lambda_.FunctionUrlCorsOptions(
                allowed_origins=["*"],
                allowed_methods=[lambda_.HttpMethod.POST],
                allowed_headers=["content-type", "authorization"],
            ),
        )

        storage.documents_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(compute.ingest_fn),
            s3.NotificationKeyFilter(prefix="knowledge/"),
        )

        api = AgentApi(
            self,
            "Api",
            query_fn=compute.query_fn,
            ingest_fn=compute.ingest_fn,
            log_retention=retention,
        )
        observability = Observability(
            self,
            "Observability",
            query_fn=compute.query_fn,
            ingest_fn=compute.ingest_fn,
            api=api.api,
            alarm_email=alarm_email,
        )

        if ctx_bool(self, "enableMacie", True):
            SensitiveDataScan(
                self,
                "Macie",
                documents_bucket=storage.documents_bucket,
                uploads_bucket=storage.uploads_bucket,
            )

        Governance(
            self,
            "Governance",
            logs_bucket=storage.logs_bucket,
            documents_bucket=storage.documents_bucket,
            uploads_bucket=storage.uploads_bucket,
            alarms_topic=observability.alarms_topic,
            monthly_budget_usd=budget_usd,
            enable_cloudtrail=ctx_bool(self, "enableCloudTrail", True),
            enable_budgets=ctx_bool(self, "enableBudgets", True),
            budget_email=alarm_email,
        )

        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "QueryFunctionUrl", value=query_url.url)
        CfnOutput(self, "ApiKeyId", value=api.api_key.key_id)
        CfnOutput(self, "DocumentsBucket", value=storage.documents_bucket.bucket_name)
        CfnOutput(self, "UploadsBucket", value=storage.uploads_bucket.bucket_name)
        CfnOutput(self, "KnowledgeBaseId", value=knowledge.knowledge_base_id)
        CfnOutput(self, "DataSourceId", value=knowledge.data_source_id)
        CfnOutput(self, "GuardrailId", value=guardrail.attr_guardrail_id)
        CfnOutput(self, "GuardrailVersion", value=guardrail_version.attr_version)
        CfnOutput(self, "AlarmsTopicArn", value=observability.alarms_topic.topic_arn)
        CfnOutput(self, "KmsKeyArn", value=storage.key.key_arn)
        CfnOutput(self, "OpenSearchCollection", value=vector_store.collection_name)
