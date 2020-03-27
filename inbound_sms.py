from serverless_sdk import tag_event

from clients import rds, twilio, kinesis
from utils.kinesis import get_payload_from_kinesis_record, get_payloads_from_kinesis_payload

def store_message(event, context):
    tag_event("store_message", "raw_event", event)

    for record in event["Records"]:
        kinesis_payload = record["kinesis"]
        sms = get_payload_from_kinesis_record(record)
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

    twilio_payloads = get_payloads_from_kinesis_payload(event)
    for sms in twilio_payloads:
        tag_event("route_message", "message_payload", sms)

        # route message to drill agent here

        # put content to send to user here
        response = sms["Body"]
        kinesis.publish_outbound_message(sms["From"], response)

    return {
        "statusCode": 200,
    }
