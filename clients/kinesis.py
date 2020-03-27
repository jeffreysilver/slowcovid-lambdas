import boto3
import os
import json
from serverless_sdk import tag_event


def publish_outbound_message(to, body):
    kinesis = boto3.client("kinesis")

    stage = os.environ.get("STAGE")
    payload = {"to": to, "body": body}
    response = kinesis.put_record(
        StreamName=f"outbound-sms-{stage}", Data=json.dumps(payload), PartitionKey=to,
    )

    tag_event("kinesis", "publish_outbound_message_response", response)

    return response
