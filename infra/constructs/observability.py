"""CloudWatch alarms, dashboard, and SNS notifications."""

from __future__ import annotations

from aws_cdk import Duration
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs

from constructs import Construct


class Observability(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        query_fn: lambda_.IFunction,
        ingest_fn: lambda_.IFunction,
        api: apigw.RestApi,
        alarm_email: str,
    ) -> None:
        super().__init__(scope, construct_id)

        self.alarms_topic = sns.Topic(
            self, "AlarmsTopic", display_name="multimodal-agentic-architecture-aws-alarms"
        )
        if alarm_email:
            self.alarms_topic.add_subscription(subs.EmailSubscription(alarm_email))

        alarm_action = cw_actions.SnsAction(self.alarms_topic)

        query_errors = query_fn.metric_errors(period=Duration.minutes(1))
        ingest_errors = ingest_fn.metric_errors(period=Duration.minutes(1))
        api_5xx = api.metric_server_error(period=Duration.minutes(1))

        for metric, name in (
            (query_errors, "QueryLambdaErrors"),
            (ingest_errors, "IngestLambdaErrors"),
            (api_5xx, "Api5xx"),
        ):
            alarm = cw.Alarm(
                self,
                name,
                metric=metric,
                threshold=1,
                evaluation_periods=1,
                datapoints_to_alarm=1,
                treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
                alarm_description=f"Alert when {name} >= 1 in a 1-minute period",
            )
            alarm.add_alarm_action(alarm_action)

        duration_alarm = cw.Alarm(
            self,
            "QueryDurationP99",
            metric=query_fn.metric_duration(statistic="p99", period=Duration.minutes(5)),
            threshold=50000,
            evaluation_periods=2,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
            alarm_description="Query Lambda p99 duration exceeds 50s",
        )
        duration_alarm.add_alarm_action(alarm_action)

        cw.Dashboard(
            self,
            "Dashboard",
            dashboard_name="MultimodalAgenticArchitectureAws",
            widgets=[
                [
                    cw.GraphWidget(title="Lambda errors", left=[query_errors, ingest_errors]),
                    cw.GraphWidget(title="API 5XX", left=[api_5xx]),
                    cw.GraphWidget(title="Query duration", left=[query_fn.metric_duration()]),
                ],
                [
                    cw.GraphWidget(title="Query invocations", left=[query_fn.metric_invocations()]),
                    cw.GraphWidget(title="Ingest invocations", left=[ingest_fn.metric_invocations()]),
                    cw.GraphWidget(title="Query throttles", left=[query_fn.metric_throttles()]),
                ],
            ],
        )
