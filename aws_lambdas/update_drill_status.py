from stopcovid.dialog.dialog import batch_from_dict
from stopcovid.utils import dynamodb as dynamodb_utils
from stopcovid.status import status


def handler(event, context):
    event_batches = [
        batch_from_dict(dynamodb_utils.deserialize(record["dynamodb"]["NewImage"]))
        for record in event["Records"]
        if record["dynamodb"].get("NewImage")
    ]

    for batch in event_batches:
        status.handle_dialog_event_batch(batch)

    return {"statusCode": 200}
