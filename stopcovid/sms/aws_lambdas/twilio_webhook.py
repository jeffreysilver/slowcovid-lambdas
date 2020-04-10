import datetime
import json
import logging
import os
from typing import Any, Dict
from urllib.parse import unquote_plus

import boto3
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from stopcovid.dialog.command_stream.publish import CommandPublisher
from stopcovid.utils import dynamodb as dynamodb_utils

from stopcovid.utils.logging import configure_logging
from stopcovid.utils.verify_deploy_stage import verify_deploy_stage

configure_logging()


def handler(event, context):
    verify_deploy_stage()
    kinesis = boto3.client("kinesis")
    stage = os.environ["STAGE"]

    form = extract_form(event)
    if not is_signature_valid(event, form, stage):
        logging.warning("signature validation failed")
        return {"statusCode": 403}

    idempotency_key = event["headers"]["I-Twilio-Idempotency-Token"]
    if already_processed(idempotency_key, stage):
        logging.info(f"Already processed webhook with idempotency key {idempotency_key}. Skipping.")
        return {"statusCode": 200}
    if "MessageStatus" in form:
        logging.info(f"Outbound message to {form['To']}: Recording STATUS_UPDATE in message log")
        kinesis.put_record(
            Data=json.dumps({"type": "STATUS_UPDATE", "payload": form}),
            PartitionKey=form["To"],
            StreamName=f"message-log-{stage}",
        )
    else:
        logging.info(f"Inbound message from {form['From']}")
        CommandPublisher().publish_process_sms_command(form["From"], form["Body"])
        logging.info(f"Logging an INBOUND_SMS message in the message log")
        kinesis.put_record(
            Data=json.dumps({"type": "INBOUND_SMS", "payload": form}),
            PartitionKey=form["From"],
            StreamName=f"message-log-{stage}",
        )

    record_as_processed(idempotency_key, stage)
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/xml"},
        "body": str(MessagingResponse()),
    }


def extract_form(event):
    # We're getting an x-www-form-url-encoded string and we need to translate it into a dict.
    # We aren't using urllib.parse.parse_qs because it gives a slightly different answer, resulting
    # in failed signature validation.

    return {
        split_pair[0]: unquote_plus(split_pair[1])
        for split_pair in [kvpair.split("=") for kvpair in event["body"].split("&")]
    }


def is_signature_valid(event: Dict[str, Any], form: Dict[str, Any], stage: str) -> bool:
    validator = RequestValidator(os.environ["TWILIO_AUTH_TOKEN"])
    url = f"https://{event['headers']['Host']}/{stage}{event['path']}"
    signature = event["headers"].get("X-Twilio-Signature")
    return validator.validate(url, form, signature)


def already_processed(idempotency_key: str, stage: str) -> bool:
    dynamodb = boto3.client("dynamodb")
    response = dynamodb.get_item(
        TableName=f"twilio-webhooks-{stage}", Key={"idempotency_key": {"S": idempotency_key}}
    )
    return "Item" in response


def record_as_processed(idempotency_key: str, stage: str):
    logging.info(f"Marking idempotency key {idempotency_key} as processed")
    dynamodb = boto3.client("dynamodb")
    dynamodb.put_item(
        TableName=f"twilio-webhooks-{stage}",
        Item=dynamodb_utils.serialize(
            {
                "idempotency_key": idempotency_key,
                "expiration_ts": int(
                    (
                        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
                    ).timestamp()
                ),
            }
        ),
    )