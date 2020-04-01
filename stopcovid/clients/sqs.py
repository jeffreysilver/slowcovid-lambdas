import boto3
import os
import json
from typing import List

from stopcovid.event_distributor.outbound_sms import OutboundSMS


def publish_outbound_sms_messages(outbound_sms_messages: List[OutboundSMS]):
    if not outbound_sms_messages:
        return

    sqs = boto3.resource("sqs")

    queue_name = f"outbound-sms-{os.getenv('STAGE')}.fifo"
    queue = sqs.get_queue_by_name(QueueName=queue_name)

    entries = [
        {
            "Id": f"{str(outbound_sms.event_id)}-{i}",
            "MessageBody": json.dumps({"To": outbound_sms.phone_number, "Body": outbound_sms.body}),
            "MessageAttributes": {
                "delay_seconds": {
                    "StringValue": str(outbound_sms.delay_seconds),
                    "DataType": "Number",
                }
            },
            "MessageDeduplicationId": f"{str(outbound_sms.event_id)}-{i}",
            "MessageGroupId": outbound_sms.phone_number,
        }
        for i, outbound_sms in enumerate(outbound_sms_messages)
    ]

    return queue.send_messages(Entries=entries)
