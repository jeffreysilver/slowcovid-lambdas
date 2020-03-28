from serverless_sdk import tag_event
from clients import lambdas
from utils.kinesis import get_payloads_from_kinesis_payload


COMMAND_TYPES = {"INBOUND_SMS"}


def handle_command(raw_event, context):
    tag_event("command_stream", "handle_command", raw_event)
    events = get_payloads_from_kinesis_payload(raw_event)
    tag_event("command_stream", "commands", events)

    for event in events:
        response = get_response(event)
        lambdas.invoke_send_message(response)

    return {"statusCode": 200}


def get_response(event):
    command_type = event["type"]
    payload = event["payload"]

    if command_type == "INBOUND_SMS":
        response = _handle_inbound_sms(payload)

    return response


def _handle_inbound_sms(sms):
    # dummy response for now
    return {"To": sms["From"], "Body": sms["Body"] + sms["Body"]}
