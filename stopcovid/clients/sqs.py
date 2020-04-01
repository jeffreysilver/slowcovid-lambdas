import boto3
import os
import json
from typing import List

from stopcovid.event_distributor.outbound_sms import OutboundSMS


def publish_outbound_sms_messages(outbound_sms_messages: List[OutboundSMS]):
    sqs = boto3.resource("sqs")

    queue_name = f"outbound-sms-{os.getenv('STAGE')}.fifo"
    queue = sqs.get_queue_by_name(QueueName=queue_name)

    entries = [
        {
            "Id": str(outbound_sms.event_id),
            "MessageBody": json.dumps({"To": outbound_sms.phone_number, "Body": outbound_sms.body}),
            "MessageDeduplicationId": str(outbound_sms.event_id),
            "MessageGroupId": outbound_sms.phone_number,
        }
        for outbound_sms in outbound_sms_messages
    ]

    return queue.send_messages(Entries=entries)
