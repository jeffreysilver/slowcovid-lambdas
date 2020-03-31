import os
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict

import requests
from marshmallow import Schema, fields, post_load


class CodeValidationPayloadSchema(Schema):
    valid = fields.Boolean(required=True)
    is_demo = fields.Boolean()
    account_info = fields.Mapping(keys=fields.Str(), allow_none=True)

    @post_load
    def make_code_validation_payload(self, data, **kwargs):
        return CodeValidationPayload(**data)


class CodeValidationPayload:
    def __init__(self, valid: bool, is_demo: Optional[bool] = False,
                 account_info: Optional[Dict[str, Any]] = None):
        self.valid = valid
        self.is_demo = is_demo
        self.account_info = account_info


class RegistrationValidator(ABC):
    @abstractmethod
    def validate_code(self, code) -> CodeValidationPayload:
        pass


class DefaultRegistrationValidator(RegistrationValidator):
    def validate_code(self, code, **kwargs) -> CodeValidationPayload:
        url = kwargs.get("url", os.getenv("REGISTRATION_VALIDATION_URL"))
        key = kwargs.get("key", os.getenv("REGISTRATION_VALIDATION_KEY"))
        response = requests.post(
            url=url,
            json={
                "code": code
            },
            headers={
                "authorization": f"Basic {key}",
                "content-type": "application/json"
            }
        )
        return CodeValidationPayloadSchema().load(response.json())
