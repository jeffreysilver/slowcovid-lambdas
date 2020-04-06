from stopcovid.dialog.models.events import batch_from_dict
from stopcovid.utils import dynamodb as dynamodb_utils


from stopcovid.event_distributor.outbound_sms import distribute_outbound_sms_events


def distribute_dialog_events(event, context):
    event_batches = [
        batch_from_dict(dynamodb_utils.deserialize(record["dynamodb"]["NewImage"]))
        for record in event["Records"]
        if record["dynamodb"].get("NewImage")
    ]

    dialog_events = []
    for batch in event_batches:
        for event in batch.events:
            dialog_events.append(event)

    distribute_outbound_sms_events(dialog_events)

    return {"statusCode": 200}
