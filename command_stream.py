from utils.kinesis import get_payload_from_kinesis_record

from dialog.dialog import (
    process_command,
    ProcessSMSMessage,
    StartDrill,
    TriggerReminder,
)
from drills.drills import drill_from_dict


def handle_command(raw_event, context):

    for record in raw_event["Records"]:
        event = get_payload_from_kinesis_record(record)
        command_type = event["type"]
        payload = event["payload"]
        sequence_number = record["kinesis"]["sequenceNumber"]

        if command_type == "INBOUND_SMS":
            process_command(
                ProcessSMSMessage(
                    phone_number=payload["From"], content=payload["Body"]
                ),
                sequence_number,
            )
        elif command_type == "START_DRILL":
            process_command(
                StartDrill(
                    phone_number=payload["phone_number"], drill=drill_from_dict(payload["drill"])
                ),
                sequence_number,
            )
        elif command_type == "TRIGGER_REMINDER":
            process_command(
                TriggerReminder(
                    phone_number=payload["phone_number"],
                    drill_id=payload["drill_id"],
                    prompt_slug=payload["prompt_slug"],
                ),
                sequence_number,
            )
        else:
            # tag_event("command_stream", "unknown command", event)
            raise RuntimeError(f"Unknown command: {command_type}")

    return {"statusCode": 200}
