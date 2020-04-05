from typing import List

from . import persistence

from stopcovid.message_log.types import (
    LogMessageCommand,
    LogMessageCommandType,
)


def _command_to_dict(command: LogMessageCommand):
    if command.command_type == LogMessageCommandType.STATUS_UPDATE:
        return {
            "twilio_message_id": command.payload["MessageSid"],
            "status": command.payload["MessageStatus"],
            "from_phone": command.payload["From"],
        }
    return {
        "twilio_message_id": command.payload["MessageSid"],
        "from_phone": command.payload.get("From"),
        "to_phone": command.payload["To"],
        "status": command.payload.get("MessageStatus") or command.payload.get("SmsStatus"),
        "body": command.payload["Body"],
    }


def log_messages(commands: List[LogMessageCommand]):
    message_repo = persistence.MessageRepository()
    message_repo.upsert_messages([_command_to_dict(c) for c in commands])
