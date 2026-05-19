import json
import os


ALLOWED_GROUP = os.environ["ALLOWED_GROUP"]
NONPROD_ACCOUNT_ID = os.environ["NONPROD_ACCOUNT_ID"]


def handler(event, context):
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})

    user_id = claims.get("sub")
    email = claims.get("email")
    raw_groups = claims.get("cognito:groups", "")

    groups = [group.strip() for group in raw_groups.split(",") if group.strip()]

    if not user_id:
        return build_response(401, {"message": "Unauthorized"})

    if ALLOWED_GROUP not in groups:
        return build_response(
            403,
            {
                "message": "Access denied",
                "required_group": ALLOWED_GROUP,
                "user_groups": groups
            }
        )

    return build_response(
        200,
        {
            "message": "User is authorized for S3 monitoring",
            "user": {
                "user_id": user_id,
                "email": email,
                "groups": groups
            },
            "target_account": NONPROD_ACCOUNT_ID,
            "resources": [
                {
                    "resource_type": "s3",
                    "bucket_name": "sample-bucket-from-next-step",
                    "tags": {
                        "Environment": "non-prod",
                        "Owner": "platform-team"
                    },
                    "status": "placeholder"
                }
            ]
        }
    )


def build_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }