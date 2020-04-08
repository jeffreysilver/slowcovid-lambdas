import json
import logging
import os
from typing import Any, Dict
from urllib.parse import unquote_plus

import boto3
from twilio.request_validator import RequestValidator

from stopcovid.dialog.command_stream.publish import CommandPublisher
from stopcovid.utils.logging import configure_logging

configure_logging()


def handler(event, context):
    kinesis = boto3.client("kinesis")
    stage = os.environ["STAGE"]

    form = extract_form(event)
    if not is_signature_valid(event, form, stage):
        logging.warning("signature validation failed")
        return {"statusCode": 403}
    if "MessageStatus" in form:
        kinesis.put_record(
            Data=json.dumps({"type": "STATUS_UPDATE", "payload": form}),
            PartitionKey=form["To"],
            StreamName=f"message-log-{stage}",
        )
        return

    CommandPublisher().publish_process_sms_command(form["From"], form["Body"])
    kinesis.put_record(
        Data=json.dumps({"type": "INBOUND_SMS", "payload": form}),
        PartitionKey=form["To"],
        StreamName=f"message-log-{stage}",
    )

    return {"statusCode": 200}


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
