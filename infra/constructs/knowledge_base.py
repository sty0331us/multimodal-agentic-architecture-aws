"""Bedrock Knowledge Base bound to OpenSearch Serverless and S3, plus Guardrails."""

from __future__ import annotations

from aws_cdk import Stack
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3

from constructs import Construct
from infra.constructs.opensearch import VectorStore


class KnowledgeBase(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        documents_bucket: s3.IBucket,
        vector_store: VectorStore,
        knowledge_base_role: iam.IRole,
        embedding_model_id: str,
        documents_prefix: str = "knowledge/",
    ) -> None:
        super().__init__(scope, construct_id)
        region = Stack.of(self).region
        embedding_arn = f"arn:aws:bedrock:{region}::foundation-model/{embedding_model_id}"

        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "KnowledgeBase",
            name="maaaws-knowledge-base",
            description="Enterprise document store for Multimodal Agentic Architecture on AWS",
            role_arn=knowledge_base_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=embedding_arn,
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=vector_store.collection_arn,
                    vector_index_name=vector_store.index_name,
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        metadata_field="AMAZON_BEDROCK_METADATA",
                        text_field="AMAZON_BEDROCK_TEXT_CHUNK",
                        vector_field="bedrock-knowledge-base-default-vector",
                    ),
                ),
            ),
        )
        self.knowledge_base.node.add_dependency(vector_store.index)

        self.data_source = bedrock.CfnDataSource(
            self,
            "S3DataSource",
            name="s3-enterprise-docs",
            description="S3 prefix ingested into the knowledge base",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            data_deletion_policy="RETAIN",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=documents_bucket.bucket_arn,
                    inclusion_prefixes=[documents_prefix],
                ),
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="FIXED_SIZE",
                    fixed_size_chunking_configuration=bedrock.CfnDataSource.FixedSizeChunkingConfigurationProperty(
                        max_tokens=300,
                        overlap_percentage=20,
                    ),
                ),
            ),
        )

    @property
    def knowledge_base_id(self) -> str:
        return self.knowledge_base.attr_knowledge_base_id

    @property
    def data_source_id(self) -> str:
        return self.data_source.attr_data_source_id


def build_guardrail(scope: Construct, construct_id: str) -> bedrock.CfnGuardrail:
    filters = []
    for filter_type in ("HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT"):
        filters.append(
            bedrock.CfnGuardrail.ContentFilterConfigProperty(
                type=filter_type,
                input_strength="HIGH",
                output_strength="HIGH",
            )
        )
    filters.append(
        bedrock.CfnGuardrail.ContentFilterConfigProperty(
            type="PROMPT_ATTACK",
            input_strength="HIGH",
            output_strength="NONE",
        )
    )
    pii_types = [
        "EMAIL",
        "PHONE",
        "NAME",
        "ADDRESS",
        "US_SOCIAL_SECURITY_NUMBER",
        "CREDIT_DEBIT_CARD_NUMBER",
        "AWS_ACCESS_KEY",
        "AWS_SECRET_KEY",
    ]
    return bedrock.CfnGuardrail(
        scope,
        construct_id,
        name="maaaws-guardrail",
        description="Responsible AI controls for Multimodal Agentic Architecture on AWS (content, PII, denied topics)",
        blocked_input_messaging=(
            "This request was blocked by the safety guardrail. Rephrase without prohibited content."
        ),
        blocked_outputs_messaging="The generated response was blocked by the safety guardrail.",
        content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(
            filters_config=filters
        ),
        sensitive_information_policy_config=bedrock.CfnGuardrail.SensitiveInformationPolicyConfigProperty(
            pii_entities_config=[
                bedrock.CfnGuardrail.PiiEntityConfigProperty(type=pii, action="ANONYMIZE")
                for pii in pii_types
            ]
        ),
        topic_policy_config=bedrock.CfnGuardrail.TopicPolicyConfigProperty(
            topics_config=[
                bedrock.CfnGuardrail.TopicConfigProperty(
                    name="Weapons and explosives",
                    definition=(
                        "Advice for building, acquiring, or using weapons, explosives, "
                        "or other violent instruments."
                    ),
                    examples=["How do I build a bomb?", "Best way to make a firearm at home"],
                    type="DENY",
                ),
                bedrock.CfnGuardrail.TopicConfigProperty(
                    name="Cyber attacks",
                    definition=(
                        "Assistance with unauthorized access, malware, exploits, or attacking systems."
                    ),
                    examples=["Write a ransomware payload", "Help me hack this website"],
                    type="DENY",
                ),
            ]
        ),
    )
