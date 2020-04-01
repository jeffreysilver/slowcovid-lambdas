from stopcovid.event_distributor.initiation import trigger_initiation_if_needed
from stopcovid.utils import dynamodb as dynamodb_utils


from stopcovid.dialog.dialog import event_from_dict

from stopcovid.event_distributor.outbound_sms import distribute_outbound_sms_events


def distribute_dialog_events(event, context):
    dialog_events = [
        event_from_dict(dynamodb_utils.deserialize(record["dynamodb"]["NewImage"]))
        for record in event["Records"]
        if record["dynamodb"].get("NewImage")
    ]

    distribute_outbound_sms_events(dialog_events)
    trigger_initiation_if_needed(dialog_events)

    return {"statusCode": 200}
