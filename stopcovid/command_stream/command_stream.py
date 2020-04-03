from typing import List

from stopcovid.dialog.dialog import process_command, ProcessSMSMessage, StartDrill, TriggerReminder
from stopcovid.drills.drills import drill_from_dict
from stopcovid.command_stream.types import InboundCommand


def handle_inbound_commands(commands: List[InboundCommand]):

    for command in commands:
        if command.command_type == "INBOUND_SMS":
            process_command(
                ProcessSMSMessage(
                    phone_number=command.payload["From"], content=command.payload["Body"]
                ),
                command.sequence_number,
            )
        elif command.command_type == "START_DRILL":
            process_command(
                StartDrill(
                    phone_number=command.payload["phone_number"],
                    drill=drill_from_dict(command.payload["drill"]),
                ),
                command.sequence_number,
            )
        elif command.command_type == "TRIGGER_REMINDER":
            process_command(
                TriggerReminder(
                    phone_number=command.payload["phone_number"],
                    drill_instance_id=command.payload["drill_instance_id"],
                    prompt_slug=command.payload["prompt_slug"],
                ),
                command.sequence_number,
            )
        else:
            raise RuntimeError(f"Unknown command: {command.command_type}")

    return {"statusCode": 200}
