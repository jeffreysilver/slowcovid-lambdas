from stopcovid.clients import twilio, kinesis, dynamo
from stopcovid.utils.sqs import get_payloads_from_sqs_event


def send_message(event, context):

    messages = get_payloads_from_sqs_event(event)

    twilio_responses = []
    for message in messages:
        idempotency_key = message["idempotency_key"]
        if dynamo.outbound_sms_idempotency_key_exists(idempotency_key):
            continue
        response = twilio.send_message(message["To"], message["Body"])
        dynamo.persist_outbound_sms_idempotency_key(idempotency_key)
        twilio_responses.append(response)

    if twilio_responses:
        kinesis.publish_log_outbound_sms(twilio_responses)

    return {
        "statusCode": 200,
    }
