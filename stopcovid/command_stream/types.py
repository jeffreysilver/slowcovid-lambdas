from dataclasses import dataclass

import enum
from marshmallow import Schema, fields, post_load


class InboundCommandType(enum.Enum):
    DRILL_STARTED = "INBOUND_SMS"
    REMINDER_TRIGGERED = "START_DRILL"
    USER_VALIDATED = "TRIGGER_REMINDER"


@dataclass
class InboundCommand:
    command_type: InboundCommandType
    sequence_number: str
    payload: dict


class InboundCommandSchema(Schema):
    command_type = fields.Str(required=True)
    sequence_number = fields.Str(required=True)
    payload = fields.Dict(required=True)

    @post_load
    def make_sms(self, data, **kwargs):
        return InboundCommand(**data)
