"""Encrypted S3 buckets for knowledge documents, user uploads, and logs."""

from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3

from constructs import Construct


class Storage(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, project_name: str) -> None:
        super().__init__(scope, construct_id)

        self.key = kms.Key(
            self,
            "DataKey",
            alias=f"alias/{project_name}/data",
            enable_key_rotation=True,
            description="CMK for Multimodal Agentic Architecture on AWS buckets, logs, and Lambda environment",
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.logs_bucket = s3.Bucket(
            self,
            "LogsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(90))],
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
        )

        self.documents_bucket = self._data_bucket("DocumentsBucket")
        self.uploads_bucket = self._data_bucket("UploadsBucket")
        self.uploads_bucket.add_lifecycle_rule(expiration=Duration.days(14), prefix="uploads/")

    def _data_bucket(self, id_: str) -> s3.Bucket:
        return s3.Bucket(
            self,
            id_,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.key,
            bucket_key_enabled=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            server_access_logs_bucket=self.logs_bucket,
            server_access_logs_prefix=f"{id_.lower()}/",
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.PUT, s3.HttpMethods.HEAD],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    exposed_headers=["ETag"],
                    max_age=3000,
                )
            ],
            lifecycle_rules=[
                s3.LifecycleRule(
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                    noncurrent_version_expiration=Duration.days(30),
                )
            ],
        )
