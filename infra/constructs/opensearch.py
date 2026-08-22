"""Amazon OpenSearch Serverless collection + vector index for Bedrock Knowledge Bases."""

from __future__ import annotations

import json

from aws_cdk import CustomResource, Duration
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_opensearchserverless as aoss
from aws_cdk import custom_resources as cr

from constructs import Construct


class VectorStore(Construct):
    index_name = "bedrock-knowledge-base-default-index"

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        collection_name: str,
        embedding_dimensions: int,
        knowledge_base_role: iam.IRole,
    ) -> None:
        super().__init__(scope, construct_id)
        self.collection_name = collection_name

        encryption = aoss.CfnSecurityPolicy(
            self,
            "EncryptionPolicy",
            name=f"{collection_name}-enc",
            type="encryption",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"],
                            }
                        ],
                        "AWSOwnedKey": True,
                    }
                ]
            ),
        )
        network = aoss.CfnSecurityPolicy(
            self,
            "NetworkPolicy",
            name=f"{collection_name}-net",
            type="network",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"],
                            },
                            {
                                "ResourceType": "dashboard",
                                "Resource": [f"collection/{collection_name}"],
                            },
                        ],
                        "AllowFromPublic": True,
                    }
                ]
            ),
        )
        self.collection = aoss.CfnCollection(
            self,
            "Collection",
            name=collection_name,
            type="VECTORSEARCH",
            description="Vector store for Multimodal Agentic Architecture on AWS",
        )
        self.collection.add_dependency(encryption)
        self.collection.add_dependency(network)

        index_fn = lambda_.Function(
            self,
            "IndexFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="aoss_index.handler",
            timeout=Duration.minutes(2),
            memory_size=256,
            code=lambda_.Code.from_asset("infra/custom_resources"),
            description="Creates the k-NN index required by Bedrock Knowledge Bases",
        )
        index_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=[self.collection.attr_arn],
            )
        )

        access = aoss.CfnAccessPolicy(
            self,
            "DataAccessPolicy",
            name=f"{collection_name}-access",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Description": "Knowledge base role + index custom resource",
                        "Rules": [
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/{collection_name}/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DeleteIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                ],
                            },
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:DeleteCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                    "aoss:DescribeCollectionItems",
                                ],
                            },
                        ],
                        "Principal": [
                            knowledge_base_role.role_arn,
                            index_fn.role.role_arn,  # type: ignore[union-attr]
                        ],
                    }
                ]
            ),
        )
        access.add_dependency(self.collection)

        provider = cr.Provider(self, "IndexProvider", on_event_handler=index_fn)
        self.index = CustomResource(
            self,
            "VectorIndex",
            service_token=provider.service_token,
            properties={
                "collectionEndpoint": self.collection.attr_collection_endpoint,
                "indexName": self.index_name,
                "dimension": embedding_dimensions,
                "accessPolicy": access.ref,
            },
        )
        self.index.node.add_dependency(access)
        self.index.node.add_dependency(self.collection)

    @property
    def collection_arn(self) -> str:
        return self.collection.attr_arn
