import json
from time import sleep
from serverless_sdk import tag_event

from stopcovid.clients import twilio, kinesis


def _get_delay_seconds(record):
    return int(record["messageAttributes"].get("delay_seconds", {}).get("stringValue", "0"))


def _send_message_to_twilio(record):
    message = json.loads(record["body"])
    delay_seconds = _get_delay_seconds(record)
    if delay_seconds:
        sleep(delay_seconds)
    return twilio.send_message(message["To"], message["Body"])


def send_sms(event, context):
    twilio_responses = [_send_message_to_twilio(record) for record in event["Records"]]
    try:
        kinesis.publish_log_outbound_sms(twilio_responses)
    except Exception:
        tag_event(
            "send_sms",
            "failed_to_write_to_kinesis_log",
            [
                {
                    "twilio_message_id": response.sid,
                    "to": response.to,
                    "body": response.body,
                    "status": response.status,
                    "error_code": response.error_code,
                    "error_message": response.error_message,
                }
                for response in twilio_responses
            ],
        )
    return {"statusCode": 200}
