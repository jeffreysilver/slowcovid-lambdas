import logging

from stopcovid.dialog.command_stream.publish import CommandPublisher
from stopcovid.utils.idempotency import IdempotencyChecker
from stopcovid.utils.kinesis import get_payload_from_kinesis_record

from stopcovid.utils.logging import configure_logging
from stopcovid.utils.verify_deploy_stage import verify_deploy_stage

configure_logging()

IDEMPOTENCY_REALM = "publish-process-sms"
IDEMPOTENCY_EXPIRATION_MINUTES = 60


def handle(event, context):
    verify_deploy_stage()
    records = event["Records"]
    publisher = CommandPublisher()
    idempotency_checker = IdempotencyChecker()
    for record in records:
        seq = record["kinesis"]["sequenceNumber"]
        raw_command = get_payload_from_kinesis_record(record)
        if raw_command["type"] == "INBOUND_SMS":
            if not idempotency_checker.already_processed(seq, IDEMPOTENCY_REALM):
                logging.info(
                    f"Creating ProcessSMSMessage command for {raw_command['payload']['From']}"
                )
                publisher.publish_process_sms_command(
                    raw_command["payload"]["From"], raw_command["payload"]["Body"]
                )
                idempotency_checker.record_as_processed(
                    seq, IDEMPOTENCY_REALM, IDEMPOTENCY_EXPIRATION_MINUTES
                )
    return {"statusCode": 200}
