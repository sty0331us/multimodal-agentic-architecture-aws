"""Amazon Macie session + scheduled classification job over project buckets."""

from __future__ import annotations

from aws_cdk import CustomResource, Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_macie as macie
from aws_cdk import aws_s3 as s3
from aws_cdk import custom_resources as cr

from constructs import Construct


class SensitiveDataScan(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        documents_bucket: s3.IBucket,
        uploads_bucket: s3.IBucket,
    ) -> None:
        super().__init__(scope, construct_id)
        account = Stack.of(self).account

        self.session = macie.CfnSession(
            self,
            "MacieSession",
            status="ENABLED",
            finding_publishing_frequency="FIFTEEN_MINUTES",
        )

        job_fn = lambda_.Function(
            self,
            "MacieJobFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="macie_job.handler",
            timeout=Duration.minutes(2),
            memory_size=256,
            code=lambda_.Code.from_asset("infra/custom_resources"),
            description="Creates a scheduled Macie classification job",
        )
        job_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "macie2:CreateClassificationJob",
                    "macie2:CancelClassificationJob",
                    "macie2:DescribeClassificationJob",
                    "macie2:GetMacieSession",
                ],
                resources=["*"],
            )
        )
        provider = cr.Provider(self, "MacieJobProvider", on_event_handler=job_fn)
        self.job = CustomResource(
            self,
            "PiiClassificationJob",
            service_token=provider.service_token,
            properties={
                "jobName": "maaaws-s3-pii-scan",
                "accountId": account,
                "buckets": [documents_bucket.bucket_name, uploads_bucket.bucket_name],
            },
        )
        self.job.node.add_dependency(self.session)
