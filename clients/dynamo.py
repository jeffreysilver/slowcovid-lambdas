import boto3
import os
import time


DYNAMO = boto3.client("dynamodb")

OUTBOUND_SMS_IDEMPOTENCY_KEY_TABLE_NAME = f"outbound-sms-idempotency-{os.getenv('STAGE')}"

def persist_outbound_sms_idempotency_key(idempotency_key):
    expire_at = time.time() + 60 * 60 * 24 # clean up idempotency keys after one day
    return DYNAMO.put_item(
        TableName=OUTBOUND_SMS_IDEMPOTENCY_KEY_TABLE_NAME, Item={
            "idempotency_key": {"S": idempotency_key},
            "expire_at": {"N": str(expire_at)},
        }
    )


def outbound_sms_idempotency_key_exists(idempotency_key):
    response = DYNAMO.get_item(
        TableName=OUTBOUND_SMS_IDEMPOTENCY_KEY_TABLE_NAME,
        Key={"idempotency_key": {"S": idempotency_key}},
        AttributesToGet=["idempotency_key"],
        ConsistentRead=True,
    )
    return bool(response.get("Item"))
