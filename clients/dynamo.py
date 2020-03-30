import boto3
import os

DYNAMO = boto3.resource("dynamodb")


def persist_outbound_sms_idempotency_key(idempotency_key):
    table_name = f"outbound-sms-idempotency-cache-{os.getenv('STAGE')}"
    return DYNAMO.put_item(
        TableName=table_name, Item={"idempotency_key": {"S": idempotency_key}}
    )


def outbound_sms_idempotency_key_exists(idempotency_key):
    table_name = f"outbound-sms-idempotency-cache-{os.getenv('STAGE')}"
    response = DYNAMO.get_item(
        TableName=table_name,
        Key={"idempotency_key": {"S": idempotency_key}},
        AttributesToGet=["idempotency_key"],
        ConsistentRead=True,
    )
    return bool(response.get("Item"))
