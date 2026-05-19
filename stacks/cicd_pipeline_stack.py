from aws_cdk import (
    Stack,
    CfnOutput,
    pipelines,
    aws_codecommit as codecommit,
)
from constructs import Construct

from stages.platform_stage import PlatformStage


class CicdPipelineStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, config: dict, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        repo_name = config["codecommit"]["repository_name"]
        branch = config["codecommit"]["branch"]
        pipeline_name = config["pipeline"]["name"]

        repository = codecommit.Repository.from_repository_name(
            self,
            "SourceRepository",
            repository_name=repo_name
        )

        source = pipelines.CodePipelineSource.code_commit(
            repository,
            branch
        )

        pipeline = pipelines.CodePipeline(
            self,
            "Pipeline",
            pipeline_name=pipeline_name,
            cross_account_keys=True,
            synth=pipelines.ShellStep(
                "Synth",
                input=source,
                commands=[
                    "python --version",
                    "node --version",
                    "npm --version",
                    "python -m pip install --upgrade pip",
                    "pip install -r requirements.txt",
                    "npm install -g aws-cdk@latest",
                    "cdk synth"
                ]
            )
        )

        pipeline.add_stage(
            PlatformStage(
                self,
                "DeployPlatform",
                config=config
            )
        )

        CfnOutput(
            self,
            "PipelineName",
            value=pipeline_name
        )

        CfnOutput(
            self,
            "RepositoryName",
            value=repo_name
        )