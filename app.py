import json
from pathlib import Path

import aws_cdk as cdk

from stacks.cicd_pipeline_stack import CicdPipelineStack


def load_config():
    config_path = Path("config/var.config.json")
    return json.loads(config_path.read_text())


config = load_config()

app = cdk.App()

region = config["region"]
accounts = config["accounts"]

CicdPipelineStack(
    app,
    "CicdPipelineStack",
    config=config,
    env=cdk.Environment(
        account=accounts["cicd"],
        region=region
    )
)

app.synth()