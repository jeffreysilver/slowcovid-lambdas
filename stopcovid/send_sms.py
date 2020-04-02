import json
from time import sleep
from serverless_sdk import tag_event  # type: ignore

from stopcovid.clients import twilio, kinesis

DELAY_SECONDS_BETWEEN_MESSAGES = 2


def _send_batch(record):
    payload = json.loads(record["body"])
    phone = payload["to"]
    messages = payload["messages"]

    twilio_responses = []
    for i, message in enumerate(messages):
        res = twilio.send_message(phone, message["body"])
        twilio_responses.append(res)

        if 0 < i < len(messages):
            sleep(DELAY_SECONDS_BETWEEN_MESSAGES)

    return twilio_responses


def send_sms(event, context):
    batches = [_send_batch(record) for record in event["Records"]]

    twilio_responses = []
    for batch in batches:
        for response in batch:
            twilio_responses.append(response)
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
