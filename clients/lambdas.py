import boto3
import json
import os


def invoke_send_message(payload):
    client = boto3.client("lambda")
    stage = os.environ["STAGE"]

    response = client.invoke(
        FunctionName=f"slowcovid-{stage}-sendMessage",
        Payload=json.dumps(payload),
        InvocationType="Event",
    )

    return response
