"""Amazon API Gateway REST API for Multimodal Agentic Architecture on AWS."""

from __future__ import annotations

from aws_cdk import Duration
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_wafv2 as wafv2

from constructs import Construct


class AgentApi(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        query_fn: lambda_.IFunction,
        ingest_fn: lambda_.IFunction,
        log_retention: logs.RetentionDays,
    ) -> None:
        super().__init__(scope, construct_id)

        access_log_group = logs.LogGroup(
            self,
            "ApiAccessLogs",
            log_group_name="/aws/apigateway/multimodal-agentic-architecture-aws",
            retention=log_retention,
        )
        self.api = apigw.RestApi(
            self,
            "RestApi",
            rest_api_name="multimodal-agentic-architecture-aws",
            description="Multimodal Agentic Architecture on AWS API (query, uploads, documents)",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=20,
                throttling_burst_limit=40,
                tracing_enabled=True,
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=False,
                metrics_enabled=True,
                access_log_destination=apigw.LogGroupLogDestination(access_log_group),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization", "X-Api-Key"],
            ),
            binary_media_types=["multipart/form-data", "image/png", "image/jpeg"],
            cloud_watch_role=True,
        )

        self.api_key = self.api.add_api_key("ClientKey", api_key_name="maaaws-client")
        plan = self.api.add_usage_plan(
            "UsagePlan",
            name="maaaws-standard",
            throttle=apigw.ThrottleSettings(rate_limit=10, burst_limit=20),
            quota=apigw.QuotaSettings(limit=5000, period=apigw.Period.MONTH),
        )
        plan.add_api_key(self.api_key)
        plan.add_api_stage(stage=self.api.deployment_stage)

        query_int = apigw.LambdaIntegration(query_fn, proxy=True, timeout=Duration.seconds(59))
        ingest_int = apigw.LambdaIntegration(ingest_fn, proxy=True, timeout=Duration.seconds(29))
        method_opts = apigw.MethodOptions(api_key_required=True)

        v1 = self.api.root.add_resource("v1")
        v1.add_resource("health").add_method("GET", query_int)
        v1.add_resource("query").add_method("POST", query_int, method_options=method_opts)
        uploads = v1.add_resource("uploads")
        uploads.add_resource("presign").add_method("POST", query_int, method_options=method_opts)
        docs = v1.add_resource("documents")
        docs.add_resource("presign").add_method("POST", ingest_int, method_options=method_opts)
        v1.add_resource("ingest").add_method("POST", ingest_int, method_options=method_opts)

        self.web_acl = wafv2.CfnWebACL(
            self,
            "WebAcl",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            scope="REGIONAL",
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="maaawsApiAcl",
                sampled_requests_enabled=True,
            ),
            name="maaaws-api-acl",
            rules=[
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedCommon",
                    priority=1,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesCommonRuleSet",
                            excluded_rules=[
                                wafv2.CfnWebACL.ExcludedRuleProperty(name="SizeRestrictions_BODY")
                            ],
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="commonRules",
                        sampled_requests_enabled=True,
                    ),
                )
            ],
        )
        wafv2.CfnWebACLAssociation(
            self,
            "WebAclAssociation",
            resource_arn=self.api.deployment_stage.stage_arn,
            web_acl_arn=self.web_acl.attr_arn,
        )

    @property
    def url(self) -> str:
        return self.api.url
