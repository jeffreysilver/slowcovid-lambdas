from typing import List

from . import persistence

from stopcovid.message_log.types import LogMessageCommand, LogMessageCommandType


def _command_to_dict(command: LogMessageCommand):
    if command.command_type == LogMessageCommandType.STATUS_UPDATE:
        return {
            "twilio_message_id": command.payload["MessageSid"],
            "status": command.payload["MessageStatus"],
            "from_number": command.payload["From"],
            "to_number": command.payload["To"],
        }
    return {
        "twilio_message_id": command.payload["MessageSid"],
        "from_number": command.payload.get("From"),
        "to_number": command.payload["To"],
        "status": command.payload.get("MessageStatus") or command.payload.get("SmsStatus"),
        "body": command.payload["Body"],
    }


def log_messages(commands: List[LogMessageCommand], db_engine_factory=None):
    message_repo = persistence.MessageRepository(engine_factory=db_engine_factory)
    message_repo.upsert_messages([_command_to_dict(c) for c in commands])
