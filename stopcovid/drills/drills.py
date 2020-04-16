import json
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, List, Dict

import boto3
from marshmallow import Schema, fields, post_load

from .localize import localize
from .response_check import is_correct_response

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def drill_from_dict(obj):
    return DrillSchema().load(obj)


class PromptMessageSchema(Schema):
    text = fields.String(required=True, allow_none=True)
    media_url = fields.URL(allow_none=True)

    @post_load
    def make_prompt_message(self, data, **kwargs):
        return PromptMessage(**data)


@dataclass
class PromptMessage:
    text: Optional[str]
    media_url: Optional[str] = None


class PromptSchema(Schema):
    slug = fields.String(required=True)
    messages = fields.List(fields.Nested(PromptMessageSchema), required=True)
    response_user_profile_key = fields.String(allow_none=True)
    correct_response = fields.String(allow_none=True)

    @post_load
    def make_prompt(self, data, **kwargs):
        return Prompt(**data)


@dataclass
class Prompt:
    slug: str
    messages: List[PromptMessage]
    response_user_profile_key: Optional[str] = None
    correct_response: Optional[str] = None
    max_failures: int = 1

    def should_advance_with_answer(self, answer: str, lang: Optional[str]) -> bool:
        if self.correct_response is None:
            return True
        return is_correct_response(answer, localize(self.correct_response, lang))

    def stores_answer(self) -> bool:
        return self.response_user_profile_key is not None


class DrillSchema(Schema):
    name = fields.String(required=True)
    slug = fields.String(required=True)
    prompts = fields.List(fields.Nested(PromptSchema), required=True)

    @post_load
    def make_drill(self, data, **kwargs):
        return Drill(**data)


@dataclass
class Drill:
    slug: str
    name: str
    prompts: List[Prompt]

    def first_prompt(self) -> Prompt:
        return self.prompts[0]

    def get_prompt(self, slug: str) -> Optional[Prompt]:
        for p in self.prompts:
            if p.slug == slug:
                return p
        raise ValueError(f"unknown prompt {slug}")

    def get_next_prompt(self, slug: str) -> Optional[Prompt]:
        return_next = False
        for p in self.prompts:
            if return_next:
                return p
            if p.slug == slug:
                return_next = True
        return None

    def to_dict(self):
        return DrillSchema().dump(self)


DRILL_CACHE: Optional[Dict[str, Drill]] = None


def get_drill(drill_key: str) -> Drill:
    if DRILL_CACHE is None:
        _populate_drill_cache()
    return DRILL_CACHE[drill_key]


def _populate_drill_cache():
    global DRILL_CACHE
    DRILL_CACHE = defaultdict(dict)  # type:ignore
    raw_drills = json.loads(_get_drill_content())
    for drill_key, raw_drill in raw_drills.items():
        DRILL_CACHE[drill_key] = DrillSchema().load(raw_drill)


def _get_drill_content() -> str:
    s3_bucket = os.getenv("DRILL_CONTENT_S3_BUCKET")
    if not s3_bucket:
        # in production, we serve from S3. The file-system JSON is useful for demo purposes.
        with open(os.path.join(__location__, "drill_content/drills.json")) as f:
            return f.read()
    s3 = boto3.resource("s3")
    drills = s3.Object(s3_bucket, "drills.json")
    return drills.get()["Body"].read().decode("utf-8")
