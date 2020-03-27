import boto3
import json
import os


def invoke_store_messages(payload):
    client = boto3.client("lambda")
    stage = os.environ["STAGE"]

    response = client.invoke(
        FunctionName=f"slowcovid-{stage}-storeOutboundSMS",
        Payload=json.dumps(payload),
        InvocationType="Event",
    )

    return response
