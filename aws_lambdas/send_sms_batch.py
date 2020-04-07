from stopcovid.send_sms.types import SMSBatchSchema
from stopcovid.send_sms.send_sms import send_sms_batches
from stopcovid.utils.logging import configure_logging

configure_logging()


def handler(event, context):
    batches = [SMSBatchSchema().loads(record["body"]) for record in event["Records"]]
    send_sms_batches(batches)
    return {"statusCode": 200}
