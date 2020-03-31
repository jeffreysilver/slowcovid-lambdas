import boto3
import os
import json
from typing import List
from dataclasses import dataclass

SQS = boto3.resource("sqs")


@dataclass
class OutboundSMS:
    event_id: str
    phone_number: str
    body: str


def publish_outbound_sms_messages(outbound_sms_messages: List[OutboundSMS]):
    queue_name = f"outbound-sms-{os.getenv('STAGE')}"
    queue = SQS.get_queue_by_name(QueueName=queue_name)

    entries = [
        {
            "Id": outbound_sms.event_id,
            "MessageBody": json.dumps({"To": outbound_sms.phone_number, "Body": outbound_sms.body}),
            "MessageAttributes": {
                "idempotency_key": {"StringValue": outbound_sms.event_id, "DataType": "String"}
            },
        }
        for outbound_sms in outbound_sms_messages
    ]

    return queue.send_messages(Entries=entries)
