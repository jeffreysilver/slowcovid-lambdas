import json
from time import sleep
from stopcovid.clients import twilio, kinesis


def _get_delay_seconds(record):
    return int(record["MessageAttributes"].get("delay_seconds", {}).get("stringValue", "0"))


def _send_message_to_twilio(record):
    message = json.loads(record["body"])
    sleep(_get_delay_seconds(record))
    return twilio.send_message(message["To"], message["Body"])


def send_sms(event, context):
    twilio_responses = [_send_message_to_twilio(record) for record in event["Records"]]

    if twilio_responses:
        kinesis.publish_log_outbound_sms(twilio_responses)

    return {"statusCode": 200}
