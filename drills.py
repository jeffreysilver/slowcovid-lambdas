import uuid
from typing import Optional

from marshmallow import Schema, fields, post_load


class PromptSchema(Schema):
    slug = fields.String(required=True)
    should_store_response = fields.Boolean()
    response_user_profile_key = fields.String()

    @post_load
    def make_prompt(self, data, **kwargs):
        return Prompt(**data)


class Prompt:
    def __init__(self,
                 slug: str,
                 should_store_response: bool = False,
                 response_user_profile_key: Optional[str] = None):
        self.slug = slug
        self.should_store_response = should_store_response
        self.response_user_profile_key = response_user_profile_key


class DrillSchema(Schema):
    drill_id = fields.UUID(required=True)

    @post_load
    def make_drill(self, data, **kwargs):
        return Drill(**data)


class Drill:
    def __init__(self, drill_id: uuid.UUID):
        self.drill_id = drill_id

    def get_prompt(self, slug: str) -> Optional[Prompt]:
        pass

    def get_next_prompt(self, slug: str) -> Optional[Prompt]:
        pass
