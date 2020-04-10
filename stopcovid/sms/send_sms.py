from time import sleep
import logging
import json


from typing import List

from . import twilio
from stopcovid.sms.types import SMSBatch

from . import publish

DELAY_SECONDS_BETWEEN_MESSAGES = 3


def _publish_send(twilio_response):
    try:
        publish.publish_outbound_sms([twilio_response])
    except Exception:
        twilio_dict = {
            "twilio_message_id": twilio_response.sid,
            "to": twilio_response.to,
            "body": twilio_response.body,
            "status": twilio_response.status,
            "error_code": twilio_response.error_code,
            "error_message": twilio_response.error_message,
        }
        logging.info(f"Failed to publisht to kinesis log: {json.dumps(twilio_dict)}")


def _send_batch(batch: SMSBatch):
    twilio_responses = []
    for i, message in enumerate(batch.messages):
        res = twilio.send_message(batch.phone_number, message.body, message.media_url)
        _publish_send(res)
        twilio_responses.append(res)

        # sleep after every  message besides the last one
        if i < len(batch.messages) - 1:
            sleep(DELAY_SECONDS_BETWEEN_MESSAGES)

    return twilio_responses


def send_sms_batches(batches: List[SMSBatch]):
    for batch in batches:
        _send_batch(batch)
