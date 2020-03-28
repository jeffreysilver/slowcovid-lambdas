import boto3
import os
import json
from serverless_sdk import tag_event


def publish_outbound_message(payload):
    kinesis = boto3.client("kinesis")

    stage = os.environ.get("STAGE")

    response = kinesis.put_record(
        StreamName=f"message-log-{stage}",
        Data=json.dumps(payload),
        PartitionKey=payload["payload"]["To"],
    )

    tag_event("kinesis", "publish_outbound_message_response", response)

    return response
