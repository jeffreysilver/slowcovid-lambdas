from serverless_sdk import tag_event


def healthcheck(event, context):
    tag_event("healthcheck")

    return {
        "statusCode": 200,
        "body": "up and at em"
    }