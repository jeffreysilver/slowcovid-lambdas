import json
import logging
import os
from urllib.parse import parse_qs, unquote_plus

import boto3
from twilio.request_validator import RequestValidator

from stopcovid.dialog.command_stream.publish import CommandPublisher
from stopcovid.utils.logging import configure_logging

configure_logging()


def handler(event, context):
    kinesis = boto3.client("kinesis")
    stage = os.getenv("STAGE")

    validator = RequestValidator(os.getenv("TWILIO_AUTH_TOKEN"))
    url = f"https://{event['headers']['Host']}/{stage}{event['path']}"
    form = {
        split_pair[0]: unquote_plus(split_pair[1])
        for split_pair in [kvpair.split("=") for kvpair in event["body"].split("&")]
    }
    signature = event["headers"].get("X-Twilio-Signature")
    if not validator.validate(url, form, signature):
        logging.warning("signature validation failed")
        return {"statusCode": 403}
    if "MessageStatus" in form:
        kinesis.put_record(
            Data=json.dumps({"type": "STATUS_UPDATE", "payload": form}),
            PartitionKey=event["To"],
            StreamName=f"message-log-{stage}",
        )
        return

    CommandPublisher().publish_process_sms_command(form["From"], form["Body"])
    return {"statusCode": 200}
