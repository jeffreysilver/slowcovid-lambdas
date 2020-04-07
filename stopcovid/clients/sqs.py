import hashlib
import random

import boto3
import os
import json
import uuid

from typing import List, Iterable
from collections import defaultdict
from stopcovid.event_distributor.outbound_sms import OutboundSMS
from stopcovid.status.drill_progress import DrillProgress


def _get_message_deduplication_id(messages):
    unique_message_ids = sorted(list(set([str(message.event_id) for message in messages])))
    combined = "-".join(unique_message_ids)
    m = hashlib.shake_256()
    m.update(combined.encode("utf-8"))
    return m.hexdigest(64)  # the length of a hex digest will be up to 64 * 2 or 128


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
            "Id": str(uuid.uuid4()),
            "MessageBody": json.dumps(
                {
                    "phone_number": phone,
                    "messages": [
                        {"body": message.body, "media_url": message.media_url}
                        for message in messages
                    ],
                }
            ),
            "MessageDeduplicationId": _get_message_deduplication_id(messages),
            "MessageGroupId": phone,
        }
        for phone, messages in phone_number_to_messages.items()
    ]

    return queue.send_messages(Entries=entries)


def publish_drills_to_trigger(
    drill_progresses: Iterable[DrillProgress], distribute_over_minutes: int
):
    sqs = boto3.resource("sqs")

    queue_name = f"drill-initiation-{os.getenv('STAGE')}"
    queue = sqs.get_queue_by_name(QueueName=queue_name)

    for drill_progress in drill_progresses:
        queue.send_message(
            MessageBody=json.dumps(
                {"idempotency_key": str(uuid.uuid4()), "drill_progress": drill_progress.to_dict()}
            ),
            DelaySeconds=random.randint(1, distribute_over_minutes * 60),
        )
