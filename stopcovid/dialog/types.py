import enum
import uuid
from abc import abstractmethod, ABC
import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from marshmallow import Schema, fields, post_load, utils
from stopcovid.drills import drills


class UserProfileSchema(Schema):
    validated = fields.Boolean(required=True)
    language = fields.Str(allow_none=True)
    name = fields.Str(allow_none=True)
    account_info = fields.Mapping(keys=fields.Str(), allow_none=True)
    is_demo = fields.Boolean()
    self_rating_1 = fields.Str(allow_none=True)
    self_rating_2 = fields.Str(allow_none=True)
    self_rating_3 = fields.Str(allow_none=True)
    self_rating_4 = fields.Str(allow_none=True)
    self_rating_5 = fields.Str(allow_none=True)
    self_rating_6 = fields.Str(allow_none=True)
    self_rating_7 = fields.Str(allow_none=True)

    @post_load
    def make_user_profile(self, data, **kwargs):
        return UserProfile(**data)


@dataclass
class UserProfile:
    validated: bool
    is_demo: bool = False
    name: Optional[str] = None
    language: Optional[str] = None
    account_info: Dict[str, Any] = field(default_factory=lambda: {})
    self_rating_1: Optional[str] = None
    self_rating_2: Optional[str] = None
    self_rating_3: Optional[str] = None
    self_rating_4: Optional[str] = None
    self_rating_5: Optional[str] = None
    self_rating_6: Optional[str] = None
    self_rating_7: Optional[str] = None

    def __str__(self):
        return f"lang={self.language}, validated={self.validated}, " f"name={self.name}"


class PromptStateSchema(Schema):
    slug = fields.Str(required=True)
    start_time = fields.DateTime(required=True)
    failures = fields.Int(allow_none=True)
    reminder_triggered = fields.Boolean(allow_none=True)

    @post_load
    def make_prompt_state(self, data, **kwargs):
        return PromptState(**data)


@dataclass
class PromptState:
    slug: str
    start_time: datetime.datetime
    last_response_time: Optional[datetime.datetime] = None
    reminder_triggered: bool = False
    failures: int = 0


class DialogStateSchema(Schema):
    phone_number = fields.Str(required=True)
    # store sequence number as a string to int conversion imprecision
    seq = fields.Str(required=True)
    user_profile = fields.Nested(UserProfileSchema, allow_none=True)
    # persist the entire drill so that modifications to drills don"t affect
    # drills that are in flight
    current_drill = fields.Nested(drills.DrillSchema, allow_none=True)
    drill_instance_id = fields.UUID(allow_none=True)
    current_prompt_state = fields.Nested(PromptStateSchema, allow_none=True)

    @post_load
    def make_dialog_state(self, data, **kwargs):
        return DialogState(**data)


@dataclass
class DialogState:
    phone_number: str
    seq: str
    user_profile: UserProfile = field(default_factory=lambda: UserProfile(validated=False))
    current_drill: Optional[drills.Drill] = None
    drill_instance_id: Optional[uuid.UUID] = None
    current_prompt_state: Optional[PromptState] = None

    def get_prompt(self) -> Optional[drills.Prompt]:
        if self.current_drill is None or self.current_prompt_state is None:
            return None
        return self.current_drill.get_prompt(self.current_prompt_state.slug)

    def get_next_prompt(self) -> Optional[drills.Prompt]:
        return self.current_drill.get_next_prompt(self.current_prompt_state.slug)

    def is_next_prompt_last(self) -> bool:
        return self.current_drill.prompts[-1].slug == self.get_next_prompt().slug

    def to_dict(self) -> Dict:
        return DialogStateSchema().dump(self)


class DialogEventType(enum.Enum):
    DRILL_STARTED = "DRILL_STARTED"
    REMINDER_TRIGGERED = "REMINDER_TRIGGERED"
    USER_VALIDATED = "USER_VALIDATED"
    USER_VALIDATION_FAILED = "USER_VALIDATION_FAILED"
    COMPLETED_PROMPT = "COMPLETED_PROMPT"
    FAILED_PROMPT = "FAILED_PROMPT"
    ADVANCED_TO_NEXT_PROMPT = "ADVANCED_TO_NEXT_PROMPT"
    DRILL_COMPLETED = "DRILL_COMPLETED"


class EventTypeField(fields.Field):
    """Field that serializes to a title case string and deserializes
    to a lower case string.
    """

    def _serialize(self, value, attr, obj, **kwargs):
        return value.name

    def _deserialize(self, value, attr, data, **kwargs):
        return DialogEventType[value]


class DialogEventSchema(Schema):
    phone_number = fields.String(required=True)
    created_time = fields.DateTime(required=True)
    event_id = fields.UUID(required=True)
    event_type = EventTypeField(required=True)
    user_profile = fields.Nested(UserProfileSchema, required=True)


class DialogEvent(ABC):
    def __init__(
        self,
        schema: Schema,
        event_type: DialogEventType,
        phone_number: str,
        user_profile: UserProfile,
        **kwargs,
    ):
        self.schema = schema
        self.phone_number = phone_number

        # relying on created time to determine ordering. We should be fine and it's simpler than
        # sequence numbers. Events are processed in order by phone number and are relatively
        # infrequent. And the lambda environment has some clock guarantees.
        self.created_time = kwargs.get("created_time", datetime.datetime.now(datetime.timezone.utc))
        self.event_id = kwargs.get("event_id", uuid.uuid4())
        self.event_type = event_type
        self.user_profile = user_profile

    @abstractmethod
    def apply_to(self, dialog_state: DialogState):
        pass

    def to_dict(self) -> Dict:
        return self.schema.dump(self)


@dataclass
class DialogEventBatch:
    events: List[DialogEvent]
    phone_number: str
    seq: str
    batch_id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_time: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def to_dict(self):
        return {
            "batch_id": str(self.batch_id),
            "seq": self.seq,
            "phone_number": self.phone_number,
            "created_time": utils.isoformat(self.created_time),
            "events": [event.to_dict() for event in self.events],
        }


class Command(ABC):
    def __init__(self, phone_number: str):
        self.phone_number = phone_number

    @abstractmethod
    def execute(self, dialog_state: DialogState) -> List[DialogEvent]:
        pass
