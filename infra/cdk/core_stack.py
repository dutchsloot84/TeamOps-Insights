"""CDK stack defining the ReleaseCopilot core infrastructure."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigateway as apigateway,
    aws_cloudwatch as cw,
    aws_cloudwatch_actions as actions,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
)
from constructs import Construct


class CoreStack(Stack):
    """Provision the ReleaseCopilot storage, secrets, and execution runtime."""

    RC_S3_PREFIX = "releasecopilot"

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_name: str,
        jira_secret_arn: Optional[str] = None,
        bitbucket_secret_arn: Optional[str] = None,
        lambda_asset_path: str = "../../dist",
        lambda_handler: str = "main.handler",
        lambda_timeout_sec: int = 180,
        lambda_memory_mb: int = 512,
        schedule_enabled: bool = False,
        schedule_cron: str | None = None,
        jira_webhook_secret_arn: Optional[str] = None,
        reconciliation_schedule_expression: str | None = None,
        enable_reconciliation_schedule: bool = True,
        reconciliation_fix_versions: Optional[str] = None,
        reconciliation_jql_template: Optional[str] = None,
        jira_base_url: Optional[str] = None,
        metrics_namespace: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        asset_path = Path(lambda_asset_path).expanduser().resolve()

        self.bucket = s3.Bucket(
            self,
            "ArtifactsBucket",
            bucket_name=bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
        )

        self.bucket.add_lifecycle_rule(
            id="RawArtifactsLifecycle",
            prefix="raw/",
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(30),
                )
            ],
            expiration=Duration.days(90),
        )

        self.bucket.add_lifecycle_rule(
            id="ReportsLifecycle",
            prefix="reports/",
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                    transition_after=Duration.days(60),
                )
            ],
        )

        self.jira_secret = self._resolve_secret(
            "JiraSecret",
            provided_arn=jira_secret_arn,
            description="Placeholder Jira OAuth secret for ReleaseCopilot",
        )
        self.bitbucket_secret = self._resolve_secret(
            "BitbucketSecret",
            provided_arn=bitbucket_secret_arn,
            description="Placeholder Bitbucket OAuth secret for ReleaseCopilot",
        )

        self.execution_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege execution role for ReleaseCopilot Lambda",
        )

        self._attach_policies()

        environment = {
            "RC_S3_BUCKET": self.bucket.bucket_name,
            "RC_S3_PREFIX": self.RC_S3_PREFIX,
            "RC_USE_AWS_SECRETS_MANAGER": "true",
        }

        clamped_timeout = max(180, min(lambda_timeout_sec, 300))
        clamped_memory = max(512, min(lambda_memory_mb, 1024))

        self.lambda_function = _lambda.Function(
            self,
            "ReleaseCopilotLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler=lambda_handler,
            code=_lambda.Code.from_asset(str(asset_path)),
            timeout=Duration.seconds(clamped_timeout),
            memory_size=clamped_memory,
            role=self.execution_role,
            environment=environment,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        self.jira_table = dynamodb.Table(
            self,
            "JiraIssuesTable",
            partition_key=dynamodb.Attribute(
                name="issue_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
        )

        self.jira_table.add_global_secondary_index(
            index_name="FixVersionIndex",
            partition_key=dynamodb.Attribute(
                name="fix_version", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(name="updated_at", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        self.jira_table.add_global_secondary_index(
            index_name="StatusIndex",
            partition_key=dynamodb.Attribute(name="status", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="updated_at", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        self.jira_table.add_global_secondary_index(
            index_name="AssigneeIndex",
            partition_key=dynamodb.Attribute(name="assignee", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="updated_at", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        self.lambda_function.add_environment("JIRA_TABLE_NAME", self.jira_table.table_name)
        self.jira_table.grant_read_data(self.lambda_function)

        webhook_secret = self._resolve_secret(
            "JiraWebhookSecret",
            provided_arn=jira_webhook_secret_arn,
            description="Shared secret used to authenticate Jira webhook deliveries",
        )

        webhook_environment = {
            "TABLE_NAME": self.jira_table.table_name,
            "LOG_LEVEL": "INFO",
            "RC_DDB_MAX_ATTEMPTS": "5",
        }
        if webhook_secret:
            webhook_environment["WEBHOOK_SECRET_ARN"] = webhook_secret.secret_arn

        self.webhook_lambda = _lambda.Function(
            self,
            "JiraWebhookLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=_lambda.Code.from_asset("services/jira_sync_webhook"),
            timeout=Duration.seconds(60),
            memory_size=256,
            environment=webhook_environment,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        self.jira_table.grant_read_write_data(self.webhook_lambda)
        if webhook_secret:
            webhook_secret.grant_read(self.webhook_lambda)

        reconciliation_environment = {
            "TABLE_NAME": self.jira_table.table_name,
            "JIRA_BASE_URL": (jira_base_url or "https://your-domain.atlassian.net"),
            "RC_DDB_MAX_ATTEMPTS": "5",
            "RC_DDB_BASE_DELAY": "0.5",
            "METRICS_NAMESPACE": metrics_namespace or "ReleaseCopilot/JiraSync",
            "JIRA_SECRET_ARN": self.jira_secret.secret_arn,
        }
        if reconciliation_fix_versions:
            reconciliation_environment["FIX_VERSIONS"] = reconciliation_fix_versions
        if reconciliation_jql_template:
            reconciliation_environment["JQL_TEMPLATE"] = reconciliation_jql_template

        self.reconciliation_dlq = sqs.Queue(
            self,
            "JiraReconciliationDLQ",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.KMS_MANAGED,
        )

        self.reconciliation_lambda = _lambda.Function(
            self,
            "JiraReconciliationLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=_lambda.Code.from_asset("services/jira_reconciliation_job"),
            timeout=Duration.seconds(300),
            memory_size=512,
            environment=reconciliation_environment,
            log_retention=logs.RetentionDays.ONE_MONTH,
            dead_letter_queue=self.reconciliation_dlq,
            dead_letter_queue_enabled=True,
            max_event_age=Duration.hours(6),
            retry_attempts=2,
        )

        self.jira_table.grant_read_write_data(self.reconciliation_lambda)
        self.jira_secret.grant_read(self.reconciliation_lambda)

        self.webhook_api = apigateway.RestApi(
            self,
            "JiraWebhookApi",
            rest_api_name="ReleaseCopilotJiraWebhook",
            deploy_options=apigateway.StageOptions(
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=False,
                metrics_enabled=True,
            ),
        )

        jira_resource = self.webhook_api.root.add_resource("jira")
        webhook_resource = jira_resource.add_resource("webhook")
        webhook_integration = apigateway.LambdaIntegration(self.webhook_lambda)
        webhook_resource.add_method("POST", webhook_integration)

        self._add_lambda_alarms()
        self._add_schedule(schedule_enabled=schedule_enabled, schedule_cron=schedule_cron)

        self._add_reconciliation_schedule(
            enable_schedule=enable_reconciliation_schedule,
            schedule_expression=reconciliation_schedule_expression,
        )

        CfnOutput(self, "ArtifactsBucketName", value=self.bucket.bucket_name)
        CfnOutput(self, "LambdaName", value=self.lambda_function.function_name)
        CfnOutput(self, "LambdaArn", value=self.lambda_function.function_arn)
        CfnOutput(self, "JiraTableName", value=self.jira_table.table_name)
        CfnOutput(self, "JiraWebhookUrl", value=self.webhook_api.url)
        CfnOutput(self, "JiraReconciliationLambdaName", value=self.reconciliation_lambda.function_name)

    def _attach_policies(self) -> None:
        prefix_objects_arn = self.bucket.arn_for_objects(f"{self.RC_S3_PREFIX}/*")
        log_group_arn = f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*"

        iam.Policy(
            self,
            "LambdaExecutionPolicy",
            statements=[
                iam.PolicyStatement(
                    sid="AllowS3ObjectAccess",
                    actions=["s3:GetObject", "s3:PutObject"],
                    resources=[prefix_objects_arn],
                ),
                iam.PolicyStatement(
                    sid="AllowS3ListArtifactsPrefix",
                    actions=["s3:ListBucket"],
                    resources=[self.bucket.bucket_arn],
                    conditions={
                        "StringLike": {
                            "s3:prefix": [
                                f"{self.RC_S3_PREFIX}/",
                                f"{self.RC_S3_PREFIX}/*",
                            ]
                        }
                    },
                ),
                iam.PolicyStatement(
                    sid="AllowSecretRetrieval",
                    actions=["secretsmanager:GetSecretValue"],
                    resources=[
                        self.jira_secret.secret_arn,
                        self.bitbucket_secret.secret_arn,
                    ],
                ),
                iam.PolicyStatement(
                    sid="AllowLambdaLogging",
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    resources=[log_group_arn],
                ),
            ],
        ).attach_to_role(self.execution_role)

    def _resolve_secret(
        self,
        construct_id: str,
        *,
        provided_arn: Optional[str],
        description: str,
    ) -> secretsmanager.ISecret:
        if provided_arn:
            return secretsmanager.Secret.from_secret_complete_arn(
                self, construct_id, provided_arn
            )
        return secretsmanager.Secret(
            self,
            construct_id,
            description=description,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True,
            ),
        )

    def _add_lambda_alarms(self) -> None:
        alarm_email = self.node.try_get_context("alarmEmail") or ""

        errors_metric = self.lambda_function.metric_errors(
            period=Duration.minutes(5), statistic="sum"
        )
        throttles_metric = self.lambda_function.metric_throttles(
            period=Duration.minutes(5), statistic="sum"
        )

        errors_alarm = cw.Alarm(
            self,
            "LambdaErrorsAlarm",
            metric=errors_metric,
            threshold=1,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )

        throttles_alarm = cw.Alarm(
            self,
            "LambdaThrottlesAlarm",
            metric=throttles_metric,
            threshold=1,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )

        if alarm_email:
            topic = sns.Topic(self, "ReleaseCopilotAlarmTopic")
            topic.add_subscription(subs.EmailSubscription(alarm_email))
            action = actions.SnsAction(topic)
            errors_alarm.add_alarm_action(action)
            throttles_alarm.add_alarm_action(action)

    def _add_schedule(self, *, schedule_enabled: bool, schedule_cron: str | None) -> None:
        """Provision the optional EventBridge rule when scheduling is enabled.

        Skipping creation when ``schedule_enabled`` is false ensures the stack
        deletes any previously-deployed schedule during updates.
        """
        if not schedule_enabled:
            return

        expression = schedule_cron or "cron(30 1 * * ? *)"
        rule = events.Rule(
            self,
            "ReleaseCopilotSchedule",
            schedule=events.Schedule.expression(expression),
        )
        rule.add_target(targets.LambdaFunction(self.lambda_function))

    def _add_reconciliation_schedule(
        self,
        *,
        enable_schedule: bool,
        schedule_expression: str | None,
    ) -> None:
        if not enable_schedule:
            return

        expression = schedule_expression or "cron(15 7 * * ? *)"
        rule = events.Rule(
            self,
            "JiraReconciliationSchedule",
            schedule=events.Schedule.expression(expression),
        )
        rule.add_target(
            targets.LambdaFunction(
                self.reconciliation_lambda,
                retry_attempts=2,
                max_event_age=Duration.hours(2),
                dead_letter_queue=self.reconciliation_dlq,
            )
        )
