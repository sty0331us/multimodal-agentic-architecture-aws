"""CloudTrail, AWS Budgets, and Cost Explorer guidance."""

from __future__ import annotations

from aws_cdk import CfnOutput
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_cloudtrail as cloudtrail
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns

from constructs import Construct


class Governance(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        logs_bucket: s3.IBucket,
        documents_bucket: s3.IBucket,
        uploads_bucket: s3.IBucket,
        alarms_topic: sns.ITopic,
        monthly_budget_usd: int,
        enable_cloudtrail: bool,
        enable_budgets: bool,
        budget_email: str,
    ) -> None:
        super().__init__(scope, construct_id)

        if enable_cloudtrail:
            trail = cloudtrail.Trail(
                self,
                "Trail",
                bucket=logs_bucket,
                s3_key_prefix="cloudtrail/",
                is_multi_region_trail=True,
                include_global_service_events=True,
                send_to_cloud_watch_logs=True,
                management_events=cloudtrail.ReadWriteType.ALL,
            )
            trail.add_s3_event_selector(
                [
                    cloudtrail.S3EventSelector(bucket=documents_bucket),
                    cloudtrail.S3EventSelector(bucket=uploads_bucket),
                ],
                include_management_events=True,
                read_write_type=cloudtrail.ReadWriteType.ALL,
            )

        if enable_budgets:
            subscribers: list[budgets.CfnBudget.SubscriberProperty] = [
                budgets.CfnBudget.SubscriberProperty(
                    subscription_type="SNS", address=alarms_topic.topic_arn
                )
            ]
            if budget_email:
                subscribers.append(
                    budgets.CfnBudget.SubscriberProperty(
                        subscription_type="EMAIL", address=budget_email
                    )
                )
            budgets.CfnBudget(
                self,
                "MonthlyBudget",
                budget=budgets.CfnBudget.BudgetDataProperty(
                    budget_name="multimodal-agentic-architecture-aws-monthly",
                    budget_type="COST",
                    time_unit="MONTHLY",
                    budget_limit=budgets.CfnBudget.SpendProperty(
                        amount=str(monthly_budget_usd), unit="USD"
                    ),
                ),
                notifications_with_subscribers=[
                    budgets.CfnBudget.NotificationWithSubscribersProperty(
                        notification=budgets.CfnBudget.NotificationProperty(
                            comparison_operator="GREATER_THAN",
                            notification_type="ACTUAL",
                            threshold=80,
                            threshold_type="PERCENTAGE",
                        ),
                        subscribers=subscribers,
                    ),
                    budgets.CfnBudget.NotificationWithSubscribersProperty(
                        notification=budgets.CfnBudget.NotificationProperty(
                            comparison_operator="GREATER_THAN",
                            notification_type="FORECASTED",
                            threshold=100,
                            threshold_type="PERCENTAGE",
                        ),
                        subscribers=subscribers,
                    ),
                ],
            )
            alarms_topic.add_to_resource_policy(
                iam.PolicyStatement(
                    sid="AllowBudgetsPublish",
                    principals=[iam.ServicePrincipal("budgets.amazonaws.com")],
                    actions=["sns:Publish"],
                    resources=[alarms_topic.topic_arn],
                )
            )

        CfnOutput(
            self,
            "CostExplorerHint",
            value="https://console.aws.amazon.com/cost-management/home#/cost-explorer",
            description="Open Cost Explorer and filter by tag Project=multimodal-agentic-architecture-aws",
        )
