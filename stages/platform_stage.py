import aws_cdk as cdk
from constructs import Construct

from stacks.shared_platform_stack import SharedPlatformStack
from stacks.nonprod_monitoring_role_stack import NonProdMonitoringRoleStack


class PlatformStage(cdk.Stage):

    def __init__(self, scope: Construct, construct_id: str, config: dict, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        region = config["region"]
        accounts = config["accounts"]
        roles = config["roles"]

        shared_invoker_role_arn = (
            f"arn:aws:iam::{accounts['shared']}:role/"
            f"{roles['shared_invoker_role_name']}"
        )

        shared_stack = SharedPlatformStack(
            self,
            "SharedPlatformStack",
            config=config,
            env=cdk.Environment(
                account=accounts["shared"],
                region=region
            )
        )

        nonprod_stack = NonProdMonitoringRoleStack(
            self,
            "NonProdMonitoringRoleStack",
            config=config,
            shared_invoker_role_arn=shared_invoker_role_arn,
            env=cdk.Environment(
                account=accounts["nonprod"],
                region=region
            )
        )

        nonprod_stack.add_dependency(shared_stack)