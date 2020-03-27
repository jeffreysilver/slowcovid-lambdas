from serverless_sdk import tag_event
from clients import twilio, rds, lambdas
from utils.kinesis import (
    get_payloads_from_kinesis_payload,
    get_payload_from_kinesis_record,
)


def send_message(event, context):
    tag_event("send_message", "raw_event", event)

    payloads = get_payloads_from_kinesis_payload(event)
    twilio_responses = [
        twilio.send_message(payload["to"], payload["body"]) for payload in payloads
    ]

    lambdas.invoke_store_messages(
        [
            {
                "twilio_message_id": response.sid,
                "to": response.to,
                "body": response.body,
                "status": response.status,
            }
            for response in twilio_responses
        ]
    )

    return {
        "statusCode": 200,
    }


def store_message(event, context):
    tag_event("store_message", "raw_event", event)
    for sms in event:
        rds.insert_message(
            sms["twilio_message_id"],
            sms["body"],
            None,  # co pilot doesnt assign a "from" number right away
            sms["to"],
            sms["status"],
        )
    return {
        "statusCode": 200,
    }


def store_status(event, context):
    tag_event("store_message", "raw_event", event)

    payloads = get_payloads_from_kinesis_payload(event)
    for payload in payloads:
        rds_response = rds.update_message(
            payload["MessageSid"], payload["MessageStatus"], payload["From"]
        )

        tag_event("store_message", "rds_response", rds_response)

    return {
        "statusCode": 200,
    }
