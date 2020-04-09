import logging

from stopcovid.dialog.models.events import batch_from_dict
from stopcovid.utils import dynamodb as dynamodb_utils


from stopcovid.send_sms.enqueue_outbound_sms import enqueue_outbound_sms_commands


def handler(event, context):
    event_batches = [
        batch_from_dict(dynamodb_utils.deserialize(record["dynamodb"]["NewImage"]))
        for record in event["Records"]
        if record["dynamodb"].get("NewImage")
    ]

    dialog_events = []
    for batch in event_batches:
        for event in batch.events:
            dialog_events.append(event)

    enqueue_outbound_sms_commands(dialog_events)
    for batch in event_batches:
        logging.info(f"Enqueue SMS commands for {batch.phone_number} at seq {batch.seq}")

    return {"statusCode": 200}
