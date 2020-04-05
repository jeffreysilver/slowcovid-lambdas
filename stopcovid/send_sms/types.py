from dataclasses import dataclass
from typing import List
from marshmallow import Schema, fields, post_load


@dataclass
class SMS:
    body: str


class SMSSchema(Schema):
    body = fields.Str(required=True)

    @post_load
    def make_sms(self, data, **kwargs):
        return SMS(**data)


@dataclass
class SMSBatch:
    phone_number: str
    messages: List[SMS]


class SMSBatchSchema(Schema):
    phone_number = fields.Str(required=True)
    messages = fields.List(fields.Nested(SMSSchema), required=True)

    @post_load
    def make_batch_sms(self, data, **kwargs):
        return SMSBatch(**data)
