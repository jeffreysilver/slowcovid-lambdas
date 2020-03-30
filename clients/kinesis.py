import boto3
import os
import json
from serverless_sdk import tag_event


KINESIS = boto3.client("kinesis")


def publish_log_outbound_message(payload):

    stage = os.environ.get("STAGE")

    response = KINESIS.put_record(
        StreamName=f"message-log-{stage}",
        Data=json.dumps(payload),
        PartitionKey=payload["payload"]["To"],
    )

    tag_event("kinesis", "publish_outbound_message_response", response)

    return response
