from stopcovid.utils import dynamodb as dynamodb_utils
from stopcovid.clients import sqs


def _get_outbound_sms_messages(dialog_events):
    # TODO: respond with the correct content
    return [
        sqs.OutboundSMS(
            event_id=event["event_id"], phone_number=event["phone_number"], body=event["event_type"]
        )
        for event in dialog_events
    ]


def distribute_dialog_events(event, context):
    dialog_events = [
        dynamodb_utils.deserialize(record["dynamodb"]["NewImage"])
        for record in event["Records"]
        if record["dynamodb"].get("NewImage")
    ]

    if dialog_events:
        sqs.publish_outbound_sms_messages(_get_outbound_sms_messages(dialog_events))

    return {"statusCode": 200}
