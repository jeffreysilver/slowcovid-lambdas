import boto3
import os
import json
import uuid

SQS = boto3.resource("sqs")


def publish_outbound_sms_messages(payloads):
    queue_name = f"outbound-sms-{os.getenv('STAGE')}"
    queue = SQS.get_queue_by_name(QueueName=queue_name)

    entries = []
    for payload in payloads:
        idempotency_key = str(uuid.uuid4())
        payload["idempotency_key"] = idempotency_key
        entries.append({"Id": idempotency_key, "MessageBody": json.dumps(payload)})

    return queue.send_messages(Entries=entries)
