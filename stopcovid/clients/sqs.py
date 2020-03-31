import boto3
import os
import json
from typing import List

from marshmallow import Schema, fields, post_load

SQS = boto3.resource("sqs")


class OutboundSMSSchema(Schema):
    event_id = fields.Str(required=True)
    phone_number = fields.Str(required=True)
    body = fields.Str(required=True)

    @post_load
    def make_outbound_sms(self, data, **kwargs):
        return OutboundSMS(**data)


class OutboundSMS:
    def __init__(self, event_id: str, phone_number: str, body: str):
        self.event_id = event_id
        self.phone_number = phone_number
        self.body = body


def publish_outbound_sms_messages(outbound_sms_messages: List[OutboundSMS]):
    queue_name = f"outbound-sms-{os.getenv('STAGE')}"
    queue = SQS.get_queue_by_name(QueueName=queue_name)

    entries = [
        {
            "Id": outbound_sms.event_id,
            "MessageBody": json.dumps(
                {
                    "To": outbound_sms.phone_number,
                    "Body": outbound_sms.body,
                    "idempotency_key": outbound_sms.event_id,
                }
            ),
        }
        for outbound_sms in outbound_sms_messages
    ]

    return queue.send_messages(Entries=entries)
