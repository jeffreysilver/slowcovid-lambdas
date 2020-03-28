import datetime
import enum
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from marshmallow import Schema, fields, post_load

import drills

VALID_OPT_IN_CODES = {"drill0"}


class UserProfileSchema(Schema):
    validated = fields.Boolean(required=True)
    language = fields.Str(allow_none=True)
    name = fields.Str(allow_none=True)
    self_rating = fields.Str(allow_none=True)

    @post_load
    def make_user_profile(self, data, **kwargs):
        return UserProfile(**data)


class UserProfile:
    def __init__(self,
                 validated: bool,
                 name: Optional[str] = None,
                 language: Optional[str] = None,
                 self_rating: Optional[str] = None
                 ):
        self.language = language
        self.validated = validated
        self.name = name
        self.self_rating = self_rating

    def __str__(self):
        return (f"lang={self.language}, validated={self.validated}, "
                f"name={self.name}, rating={self.self_rating}")


class PromptStateSchema(Schema):
    slug = fields.Str(required=True)
    start_time = fields.DateTime(required=True)
    failures = fields.Int(allow_none=True)
    reminder_triggered = fields.Boolean(allow_none=True)

    @post_load
    def make_prompt_state(self, data, **kwargs):
        return PromptState(**data)


class PromptState:
    def __init__(self, slug: str, start_time: datetime.datetime,
                 reminder_triggered: bool = False, failures: int = 0):
        self.slug = slug
        self.failures = failures
        self.start_time = start_time
        self.reminder_triggered = reminder_triggered


class DialogStateSchema(Schema):
    phone_number = fields.Str(required=True)
    user_profile = fields.Nested(UserProfileSchema, allow_none=True)
    # persist the entire drill so that modifications to drills don"t affect
    # drills that are in flight
    current_drill = fields.Nested(drills.DrillSchema, allow_none=True)
    current_prompt_state = fields.Nested(PromptStateSchema, allow_none=True)
    completed_drills = fields.List(fields.Nested(drills.DrillSchema), allow_none=True)

    @post_load
    def make_dialog_state(self, data, **kwargs):
        return DialogState(**data)


class DialogState:
    def __init__(self,
                 phone_number: str,
                 user_profile: Optional[UserProfile] = None,
                 current_drill: Optional[drills.Drill] = None,
                 current_prompt_state: Optional[PromptState] = None,
                 completed_drills: List[drills.Drill] = None):
        self.phone_number = phone_number
        self.user_profile = user_profile or UserProfile(validated=False)
        self.current_drill = current_drill
        self.current_prompt_state = current_prompt_state
        self.completed_drills = completed_drills or []

    def get_prompt(self) -> Optional[drills.Prompt]:
        if self.current_drill is None or self.current_prompt_state is None:
            return None
        return self.current_drill.get_prompt(self.current_prompt_state.slug)

    def get_next_prompt(self) -> Optional[drills.Prompt]:
        return self.current_drill.get_next_prompt(self.current_prompt_state.slug)


class DialogEventType(enum.Enum):
    DRILL_STARTED = "DRILL_STARTED"
    REMINDER_TRIGGERED = "REMINDER_TRIGGERED"
    USER_CREATED = "USER_CREATED"
    USER_CREATION_FAILED = "USER_CREATION_FAILED"
    COMPLETED_PROMPT = "COMPLETED_PROMPT"
    FAILED_PROMPT = "FAILED_PROMPT"
    ADVANCED_TO_NEXT_PROMPT = "ADVANCED_TO_NEXT_PROMPT"
    DRILL_COMPLETED = "DRILL_COMPLETED"


class DialogEvent(ABC):
    def __init__(self, event_type: DialogEventType, phone_number: str):
        self.phone_number = phone_number
        self.datetime = datetime.datetime.utcnow()
        self.event_type = event_type

    @abstractmethod
    def apply_to(self, dialog_state: DialogState):
        pass


class DialogRepository(ABC):
    @abstractmethod
    def fetch_dialog_state(self, phone_number: str) -> DialogState:
        pass

    @abstractmethod
    def persist_dialog_state(self, events: List[DialogEvent], dialog_state: DialogState):
        pass


class Command(ABC):
    def __init__(self, phone_number: str):
        self.phone_number = phone_number

    @abstractmethod
    def execute(self, dialog_state: DialogState) -> List[DialogEvent]:
        pass


def process_command(command: Command, repo: DialogRepository = None):
    if repo is None:
        repo = DynamoDBDialogRepository()
    dialog_state = repo.fetch_dialog_state(command.phone_number)
    events = command.execute(dialog_state)
    for event in events:
        event.apply_to(dialog_state)
    repo.persist_dialog_state(events, dialog_state)


class StartDrill(Command):
    def __init__(self, phone_number: str, drill: drills.Drill):
        super().__init__(phone_number)
        self.drill = drill

    def execute(self, dialog_state: DialogState) -> List[DialogEvent]:
        return [DrillStarted(self.phone_number, self.drill)]


class DrillStarted(DialogEvent):
    def __init__(self, phone_number: str, drill: drills.Drill):
        super().__init__(DialogEventType.DRILL_STARTED, phone_number)
        self.drill = drill
        self.prompt = drill.first_prompt()

    def apply_to(self, dialog_state: DialogState):
        dialog_state.current_drill = self.drill
        dialog_state.current_prompt_state = PromptState(self.prompt.slug, start_time=self.datetime)


class TriggerReminder(Command):
    def __init__(self, phone_number: str, drill_id: uuid.UUID, prompt_slug: str):
        super().__init__(phone_number)
        self.prompt_slug = prompt_slug
        self.drill_id = drill_id

    def execute(self, dialog_state: DialogState) -> List[DialogEvent]:
        drill = dialog_state.current_drill
        if drill is None or drill.drill_id != self.drill_id:
            return []

        prompt = dialog_state.current_prompt_state
        if prompt is None or prompt.slug != self.prompt_slug:
            return []

        if prompt.reminder_triggered:
            # to ensure idempotence
            return []

        return [ReminderTriggered(self.phone_number)]


class ReminderTriggered(DialogEvent):
    def __init__(self, phone_number: str):
        super().__init__(DialogEventType.REMINDER_TRIGGERED, phone_number)

    def apply_to(self, dialog_state: DialogState):
        dialog_state.current_prompt_state.reminder_triggered = True


class ProcessSMSMessage(Command):
    def __init__(self, phone_number: str, content: str):
        super().__init__(phone_number)
        self.content = content.strip()
        self.content_lower = self.content.lower()

    def execute(self, dialog_state: DialogState) -> List[DialogEvent]:
        if not dialog_state.user_profile.validated:
            if self.content_lower in VALID_OPT_IN_CODES:
                return [UserCreated(self.phone_number)]
            return [UserCreationFailed(self.phone_number)]

        prompt = dialog_state.get_prompt()
        if prompt is None:
            return []
        events = []
        if prompt.should_advance_with_answer(self.content_lower):
            events.append(CompletedPrompt(self.phone_number, prompt, self.content))
            should_advance = True
        else:
            should_advance = dialog_state.current_prompt_state.failures >= prompt.max_failures
            events.append(FailedPrompt(self.phone_number, prompt, abandoned=should_advance))

        if should_advance:
            next_prompt = dialog_state.get_next_prompt()
            if next_prompt is None:
                events.append(DrillCompleted(self.phone_number, dialog_state.current_drill))
            else:
                events.append(AdvancedToNextPrompt(self.phone_number, next_prompt))
        return events


class UserCreated(DialogEvent):
    def __init__(self, phone_number: str):
        super().__init__(DialogEventType.USER_CREATED, phone_number)

    def apply_to(self, dialog_state: DialogState):
        dialog_state.user_profile.validated = True


class UserCreationFailed(DialogEvent):
    def __init__(self, phone_number: str):
        super().__init__(DialogEventType.USER_CREATION_FAILED, phone_number)

    def apply_to(self, dialog_state: DialogState):
        pass


class CompletedPrompt(DialogEvent):
    def __init__(self, phone_number: str, prompt: drills.Prompt, response: str):
        super().__init__(DialogEventType.COMPLETED_PROMPT, phone_number)
        self.prompt = prompt
        self.response = response

    def apply_to(self, dialog_state: DialogState):
        dialog_state.current_prompt_state = None
        if self.prompt.response_user_profile_key:
            setattr(dialog_state.user_profile, self.prompt.response_user_profile_key, self.response)


class FailedPrompt(DialogEvent):
    def __init__(self, phone_number: str, prompt: drills.Prompt, abandoned: bool):
        super().__init__(DialogEventType.FAILED_PROMPT, phone_number)
        self.prompt = prompt
        self.abandoned = abandoned

    def apply_to(self, dialog_state: DialogState):
        if self.abandoned:
            dialog_state.current_prompt_state = None
        else:
            dialog_state.current_prompt_state.failures += 1


class AdvancedToNextPrompt(DialogEvent):
    def __init__(self, phone_number: str, prompt: drills.Prompt):
        super().__init__(DialogEventType.ADVANCED_TO_NEXT_PROMPT, phone_number)
        self.prompt = prompt

    def apply_to(self, dialog_state: DialogState):
        dialog_state.current_prompt_state = PromptState(self.prompt.slug, start_time=self.datetime)


class DrillCompleted(DialogEvent):
    def __init__(self, phone_number: str, drill: drills.Drill):
        super().__init__(DialogEventType.DRILL_COMPLETED, phone_number)
        self.drill = drill

    def apply_to(self, dialog_state: DialogState):
        dialog_state.completed_drills.append(dialog_state.current_drill)
        dialog_state.current_drill = None


class DynamoDBDialogRepository(DialogRepository):
    def fetch_dialog_state(self, phone_number: str) -> DialogState:
        pass

    def persist_dialog_state(self, events: List[DialogEvent], dialog_state: DialogState):
        pass

    def create_tables(self):
        pass
