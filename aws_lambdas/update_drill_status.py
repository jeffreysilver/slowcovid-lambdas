from stopcovid.dialog.models.events import batch_from_dict
from stopcovid.utils import dynamodb as dynamodb_utils
from stopcovid.status import status


def handler(event, context):
    event_batches = [
        batch_from_dict(dynamodb_utils.deserialize(record["dynamodb"]["NewImage"]))
        for record in event["Records"]
        if record["dynamodb"].get("NewImage")
    ]

    status.handle_dialog_event_batches(event_batches)

    return {"statusCode": 200}
