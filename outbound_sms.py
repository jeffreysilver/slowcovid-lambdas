from serverless_sdk import tag_event
from clients import twilio


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
        },
    )

    return {
        "statusCode": 200,
    }
