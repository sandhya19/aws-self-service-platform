from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_cognito as cognito,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_iam as iam,
)
from constructs import Construct


class SharedPlatformStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, config: dict, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        app_name = config["app_name"]
        paths = config["paths"]
        cognito_config = config["cognito"]
        roles = config["roles"]
        nonprod_account_id = config["accounts"]["nonprod"]

        ui_bucket = s3.Bucket(
            self,
            "UiBucket",
            bucket_name=None,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        origin_access_identity = cloudfront.OriginAccessIdentity(
            self,
            "UiOriginAccessIdentity"
        )

        ui_bucket.grant_read(origin_access_identity)

        distribution = cloudfront.Distribution(
            self,
            "UiDistribution",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    ui_bucket,
                    origin_access_identity=origin_access_identity
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
            ),
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                )
            ]
        )

        s3_deployment.BucketDeployment(
            self,
            "DeployUi",
            sources=[
                s3_deployment.Source.asset(paths["frontend_build"])
            ],
            destination_bucket=ui_bucket,
            distribution=distribution,
            distribution_paths=["/*"]
        )

        user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"{app_name}-users",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(
                    required=True,
                    mutable=True
                )
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=10,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY
        )

        # user_pool.add_domain(
        #     "UserPoolDomain",
        #     cognito_domain=cognito.CognitoDomainOptions(
        #         domain_prefix=cognito_config["domain_prefix"] + "-" + self.account
        #     )
        # )

        callback_url = f"https://{distribution.distribution_domain_name}"

        user_pool_client = user_pool.add_client(
            "UserPoolClient",
            user_pool_client_name=f"{app_name}-ui-client",
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                user_password=True
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    implicit_code_grant=True
                ),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE
                ],
                callback_urls=[callback_url],
                logout_urls=[callback_url]
            ),
            prevent_user_existence_errors=True
        )

        cognito.UserPoolGroup(
            self,
            "S3ViewerGroup",
            user_pool=user_pool,
            group_name=cognito_config["viewer_group_name"],
            description="Users allowed to view S3 monitoring data in non-prod"
        )

        get_resources_function = lambda_.Function(
            self,
            "GetResourcesFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset(paths["get_resources_lambda"]),
            timeout=Duration.seconds(30),
            environment={
                "ALLOWED_GROUP": cognito_config["viewer_group_name"],
                "NONPROD_ACCOUNT_ID": nonprod_account_id
            }
        )

        shared_invoker_role = iam.Role(
            self,
            "SharedMonitoringInvokerRole",
            role_name=roles["shared_invoker_role_name"],
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            description="Role used by shared Step Functions to invoke target account monitoring"
        )

        shared_invoker_role.add_to_policy(
            iam.PolicyStatement(
                actions=["sts:AssumeRole"],
                resources=[
                    f"arn:aws:iam::{nonprod_account_id}:role/{roles['nonprod_monitoring_role_name']}"
                ]
            )
        )

        api = apigateway.RestApi(
            self,
            "MonitoringApi",
            rest_api_name=f"{app_name}-api",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"]
            )
        )

        authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "ApiAuthorizer",
            cognito_user_pools=[user_pool]
        )

        s3_resource = api.root.add_resource("s3")

        s3_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_resources_function),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=authorizer
        )

        login_url = (
            f"https://{cognito_config['domain_prefix']}.auth.{self.region}.amazoncognito.com/login"
            f"?client_id={user_pool_client.user_pool_client_id}"
            f"&response_type=token"
            f"&scope=email+openid+profile"
            f"&redirect_uri=https://{distribution.distribution_domain_name}"
        )

        CfnOutput(self, "CloudFrontUrl", value=callback_url)
        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
        CfnOutput(self, "CognitoLoginUrl", value=login_url)
        CfnOutput(self, "SharedInvokerRoleArn", value=shared_invoker_role.role_arn)