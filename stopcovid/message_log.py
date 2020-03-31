from stopcovid.utils.kinesis import get_payloads_from_kinesis_event

from stopcovid.clients import rds


def log_message(raw_event, context):
    events = get_payloads_from_kinesis_event(raw_event)

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
