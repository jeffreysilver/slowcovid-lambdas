from serverless_sdk import tag_event


def healthcheck(event, context):
    return {
        "statusCode": 200,
        "body": "https://i0.wp.com/media1.giphy.com/media/dkGhBWE3SyzXW/giphy.gif?zoom=2"
    }