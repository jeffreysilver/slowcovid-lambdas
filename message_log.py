from serverless_sdk import tag_event
from utils.kinesis import get_payloads_from_kinesis_event

from clients import rds


def log_message(raw_event, context):
    tag_event("log_message", "raw_event", raw_event)

    events = get_payloads_from_kinesis_event(raw_event)

    tag_event("log_message", "events", events)

    for event in events:
        payload = event["payload"]

        if event["type"] == "STATUS_UPDATE":
            rds.update_message(
                payload["MessageSid"], payload["MessageStatus"], payload["From"]
            )
        else:
            rds.insert_message(
                payload["MessageSid"],
                payload["Body"],
                payload.get("From", ""),
                payload["To"],
                payload.get("MessageStatus") or payload.get("SmsStatus"),
            )
