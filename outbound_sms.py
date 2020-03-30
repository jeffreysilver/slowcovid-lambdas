from serverless_sdk import tag_event

from clients import twilio, kinesis, dynamo
from utils.sqs import get_payloads_from_sqs_event


def send_message(event, context):
    tag_event("send_message", "raw_event", event)

    messages = get_payloads_from_sqs_event(event)

    twilio_responses = []
    for message in messages:
        idempotency_key = message["idempotency_key"]
        if dynamo.outbound_sms_idempotency_key_exists(idempotency_key):
            tag_event("send_message", "idempotency_key exists", message)
            continue
        response = twilio.send_message(message["To"], message["Body"])
        dynamo.persist_outbound_sms_idempotency_key(idempotency_key)
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


    return {
        "statusCode": 200,
    }
