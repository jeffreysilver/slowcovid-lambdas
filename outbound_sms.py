from serverless_sdk import tag_event
from clients import twilio, kinesis
from utils.sqs import get_payloads_from_sqs_event


def send_message(event, context):
    tag_event("send_message", "raw_event", event)

    messages = get_payloads_from_sqs_event(event)
    for message in messages:
        response = twilio.send_message(message["To"], message["Body"])
        kinesis.publish_log_outbound_message(
            {
                "type": "OUTBOUND_SMS",
                "payload": {
                    "MessageSid": response.sid,
                    "To": response.to,
                    "Body": response.body,
                    "MessageStatus": response.status,
                },
            }
        )
        tag_event(
            "send_message",
            "twilio_response",
            {
                "twilio_message_id": response.sid,
                "to": response.to,
                "body": response.body,
                "status": response.status,
                "error_code": response.error_code,
                "error_message": response.error_message,
            },
        )

    return {
        "statusCode": 200,
    }
