import boto3
import os
import json
import uuid


def publish_outbound_messages(payloads):
    sqs = boto3.resource("sqs")
    queue_name = f"outbound-sms-{os.getenv('STAGE')}"
    queue = sqs.get_queue_by_name(QueueName=queue_name)
    entries = [
        {"MessageBody": json.dumps(payload), "Id": str(uuid.uuid4())}
        for payload in payloads
    ]

    return queue.send_messages(Entries=entries)
