import datetime
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from marshmallow import Schema, fields, post_load

from . import drills

VALID_OPT_IN_CODES = set('OPT-IN')


class UserProfileSchema(Schema):
    validated = fields.Boolean(required=True)
    language = fields.Str()

    @post_load
    def make_user_profile(self, data, **kwargs):
        return UserProfile(**data)


class UserProfile:
    def __init__(self, validated: bool, language: Optional[str] = None):
        self.language = language
        self.validated = validated


class PromptStateSchema(Schema):
    slug = fields.Str(required=True)
    start_time = fields.DateTime(required=True)
    failures = fields.Int()
    reminder_triggered = fields.Boolean()

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
    user_profile = fields.Nested(UserProfileSchema)
    # persist the entire drill so that modifications to drills don't affect
    # drills that are in flight
    current_drill = fields.Nested(drills.DrillSchema)
    current_prompt_state = fields.Nested(PromptStateSchema)
    completed_drills = fields.List(fields.UUID())

    @post_load
    def make_dialog_state(self, data, **kwargs):
        return DialogState(**data)


class DialogState:
    def __init__(self,
                 phone_number: str,
                 user_profile: Optional[UserProfile] = None,
                 current_drill: Optional[drills.Drill] = None,
                 current_prompt_state: Optional[PromptState] = None,
                 completed_drills: List[uuid.UUID] = None):
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


class DialogEvent(ABC):
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.datetime = datetime.datetime.utcnow()

    @abstractmethod
    def apply_to(self, dialog_state: DialogState):
        pass


class Command(ABC):
    def __init__(self, phone_number: str):
        self.phone_number = phone_number

    @abstractmethod
    def execute(self, dialog_state: DialogState) -> List[DialogEvent]:
        pass


def process_command(command: Command):
    dialog_state = _fetch_dialog_state(command.phone_number)
    events = command.execute(dialog_state)
    for event in events:
        event.apply_to(dialog_state)
    _persist_dialog_state(events, dialog_state)


class StartDrill(Command):
    def __init__(self, phone_number: str, drill: drills.Drill):
        super().__init__(phone_number)
        self.drill = drill

    def execute(self, dialog_state: DialogState) -> List[DialogEvent]:
        return [DrillStarted(self.phone_number, self.drill)]


class DrillStarted(DialogEvent):
    def __init__(self, phone_number, drill):
        super().__init__(phone_number)
        self.drill = drill

    def apply_to(self, dialog_state: DialogState):
        dialog_state.current_drill = self.drill


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
        super().__init__(phone_number)

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
        events = []
        if prompt.should_advance_with_answer(self.content_lower):
            events.append(CompletedPrompt(self.phone_number, prompt, self.content))
            should_advance = True
        else:
            should_advance = dialog_state.current_prompt_state.failures >= prompt.max_failures
            events.append(FailedPrompt(self.phone_number, prompt, abandon=should_advance))

        if should_advance:
            next_prompt = dialog_state.get_next_prompt()
            if next_prompt is not None:
                events.append(BeganPrompt(self.phone_number, next_prompt))
        return events


class UserCreated(DialogEvent):
    def __init__(self, phone_number: str):
        super().__init__(phone_number)

    def apply_to(self, dialog_state: DialogState):
        dialog_state.user_profile.validated = True


class UserCreationFailed(DialogEvent):
    def __init__(self, phone_number: str):
        super().__init__(phone_number)

    def apply_to(self, dialog_state: DialogState):
        pass


class CompletedPrompt(DialogEvent):
    def __init__(self, phone_number: str, prompt: drills.Prompt, response: str):
        super().__init__(phone_number)
        self.prompt = prompt
        self.response = response

    def apply_to(self, dialog_state: DialogState):
        dialog_state.current_prompt_state = None
        if self.prompt.should_store_response:
            setattr(dialog_state.user_profile, self.prompt.response_user_profile_key, self.response)


class FailedPrompt(DialogEvent):
    def __init__(self, phone_number: str, prompt: drills.Prompt, abandon: bool):
        super().__init__(phone_number)
        self.prompt = prompt
        self.abandon = abandon

    def apply_to(self, dialog_state: DialogState):
        if self.abandon:
            dialog_state.current_prompt_state = None
        else:
            dialog_state.current_prompt_state.failures += 1


class BeganPrompt(DialogEvent):
    def __init__(self, phone_number: str, prompt: drills.Prompt):
        super().__init__(phone_number)
        self.prompt = prompt

    def apply_to(self, dialog_state: DialogState):
        dialog_state.current_prompt_state = PromptState(self.prompt.slug, start_time=self.datetime)


def _fetch_dialog_state(phone_number: str) -> Optional[DialogState]:
    pass


def _persist_dialog_state(events: List[DialogEvent], dialog_state: DialogState):
    if not events:
        # if nothing has happened don't persist anything
        return
    # otherwise persist


def _create_tables():
    pass
