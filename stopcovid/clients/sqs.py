import boto3
import os
import json
import re

from typing import List
from collections import defaultdict
from stopcovid.event_distributor.outbound_sms import OutboundSMS


def _get_message_deduplication_id(messages):
    unique_message_ids = sorted(list(set([str(message.event_id) for message in messages])))
    return "-".join(unique_message_ids)


def publish_outbound_sms_messages(outbound_sms_messages: List[OutboundSMS]):
    if not outbound_sms_messages:
        return

    sqs = boto3.resource("sqs")

    queue_name = f"outbound-sms-{os.getenv('STAGE')}.fifo"
    queue = sqs.get_queue_by_name(QueueName=queue_name)

    phone_number_to_messages = defaultdict(list)
    for message in outbound_sms_messages:
        phone_number_to_messages[message.phone_number].append(message)

    entries = [
        {
            "Id": re.sub("[^0-9]", "", phone),
            "MessageBody": json.dumps(
                {"to": phone, "messages": [{"body": message.body} for message in messages]}
            ),
            "MessageDeduplicationId": _get_message_deduplication_id(messages),
            "MessageGroupId": phone,
        }
        for phone, messages in phone_number_to_messages.items()
    ]

    return queue.send_messages(Entries=entries)
