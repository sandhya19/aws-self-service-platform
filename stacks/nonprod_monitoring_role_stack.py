from aws_cdk import (
    Stack,
    CfnOutput,
    aws_iam as iam,
)
from constructs import Construct


class NonProdMonitoringRoleStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: dict,
        shared_invoker_role_arn: str,
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        role_name = config["roles"]["nonprod_monitoring_role_name"]

        monitoring_role = iam.Role(
            self,
            "NonProdMonitoringInvokeRole",
            role_name=role_name,
            assumed_by=iam.ArnPrincipal(shared_invoker_role_arn),
            description="Role trusted by shared account for non-prod monitoring"
        )

        monitoring_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListAllMyBuckets",
                    "s3:GetBucketLocation",
                    "s3:GetBucketTagging"
                ],
                resources=["*"]
            )
        )

        monitoring_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "states:StartExecution",
                    "states:DescribeExecution",
                    "states:StopExecution"
                ],
                resources=[
                    f"arn:aws:states:{self.region}:{self.account}:stateMachine:S3MonitoringStateMachine",
                    f"arn:aws:states:{self.region}:{self.account}:execution:S3MonitoringStateMachine:*"
                ]
            )
        )

        CfnOutput(
            self,
            "NonProdMonitoringRoleArn",
            value=monitoring_role.role_arn
        )