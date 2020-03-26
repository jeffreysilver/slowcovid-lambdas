from serverless_sdk import tag_event
import ast
from base64 import b64decode
from clients import rds


def _get_twilio_payload_from_record(record):
    twilio_payload_bytes = b64decode(record["kinesis"]["data"])
    return ast.literal_eval(twilio_payload_bytes.decode("UTF-8"))


def _extract_twilio_payloads_from_kinesis_payload(kinesis_payload):
    records = kinesis_payload["Records"]
    return [_get_twilio_payload_from_record(record) for record in records]


def store_message(event, context):
    tag_event("store_message", "raw_event", event)

    for record in event["Records"]:
        kinesis_payload = record["kinesis"]
        sms = _get_twilio_payload_from_record(record)
        tag_event("store_message", "message_payload", sms)
        rds_response = rds.insert_message(
            sms["MessageSid"],
            sms["Body"],
            sms["From"],
            sms["To"],
            sms["SmsStatus"],
            kinesis_payload["approximateArrivalTimestamp"],
            kinesis_payload["sequenceNumber"],
        )
        tag_event("store_message", "rds_response", rds_response)

    return {
        "statusCode": 200,
    }


def route_message(event, context):
    tag_event("route_message", "raw_event", event)

    twilio_payloads = _extract_twilio_payloads_from_kinesis_payload(event)
    for sms in twilio_payloads:
        tag_event("route_message", "message_payload", sms)

        # route message to drill agent here

    return {
        "statusCode": 200,
    }
