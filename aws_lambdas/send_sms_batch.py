from stopcovid.outbound_sms.types import SMSBatchSchema
from stopcovid.outbound_sms.send_sms import send_sms_batches


def handler(event, context):
    batches = [SMSBatchSchema().loads(record["body"]) for record in event["Records"]]
    send_sms_batches(batches)
    return {"statusCode": 200}
