from serverless_sdk import tag_event
from clients import twilio, kinesis


def send_message(event, context):
    tag_event("send_message", "raw_event", event)

    response = twilio.send_message(event["To"], event["Body"])

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

    kinesis.publish_outbound_message(
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

    return {
        "statusCode": 200,
    }
