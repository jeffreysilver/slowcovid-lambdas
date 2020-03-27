from serverless_sdk import tag_event
from clients import twilio

from utils.kinesis import get_payloads_from_kinesis_payload


def send_message(event, context):
    tag_event("send_message", "raw_event", event)

    payloads = get_payloads_from_kinesis_payload(event)
    twilio_responses = [
        twilio.send_message(payload["to"], payload["body"]) for payload in payloads
    ]

    tag_event("send_message", "twilio_responses", twilio_responses)

    return {
        "statusCode": 200,
    }
