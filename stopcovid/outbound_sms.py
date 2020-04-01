from serverless_sdk import tag_event  # type: ignore
import json

from stopcovid.clients import twilio, kinesis


def send_message(event, context):
    tag_event("send_message", "raw_event", event)

    twilio_responses = []
    for record in event["Records"]:
        message = json.loads(record["body"])
        response = twilio.send_message(message["To"], message["Body"])
        twilio_responses.append(response)

    if twilio_responses:
        kinesis_response = kinesis.publish_log_outbound_sms(twilio_responses)
        tag_event("send_message", "publish_log_message_response", kinesis_response)

    tag_event(
        "send_message",
        "twilio_responses",
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
