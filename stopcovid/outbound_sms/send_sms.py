from time import sleep
import logging
import json


from typing import List

from stopcovid.clients import twilio, kinesis
from stopcovid.outbound_sms.types import SMSBatchSchema, SMSBatch

DELAY_SECONDS_BETWEEN_MESSAGES = 3


def _send_batch(batch: SMSBatch):
    twilio_responses = []
    for i, message in enumerate(batch.messages):
        res = twilio.send_message(batch.phone_number, message.body)
        twilio_responses.append(res)

        # sleep after every  message besides the last one
        if i < len(batch.messages) - 1:
            sleep(DELAY_SECONDS_BETWEEN_MESSAGES)

    return twilio_responses


def send_sms_batches(batches: List[SMSBatch]):
    twilio_batches = [_send_batch(batch) for batch in batches]

    twilio_responses = [response for batch in twilio_batches for response in batch]

    try:
        kinesis.publish_log_outbound_sms(twilio_responses)
    except Exception:
        formatted_twilio_responses = [
            {
                "twilio_message_id": response.sid,
                "to": response.to,
                "body": response.body,
                "status": response.status,
                "error_code": response.error_code,
                "error_message": response.error_message,
            }
            for response in twilio_responses
        ]
        logging.info(
            f"send_sms_failed_to_write_to_kinesis_log: {json.dumps(formatted_twilio_responses)}"
        )


def send_sms_handler(event, context):
    batches = [SMSBatchSchema().loads(record["body"]) for record in event["Records"]]
    send_sms_batches(batches)
    return {"statusCode": 200}
