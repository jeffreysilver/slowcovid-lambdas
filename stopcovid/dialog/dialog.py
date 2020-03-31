import logging
import uuid
from copy import deepcopy
from typing import List, Dict, Any, Optional

from marshmallow import fields, post_load

from stopcovid.drills import drills
from .persistence import DialogRepository, DynamoDBDialogRepository
from . import types
from .registration import (
    RegistrationValidator,
    DefaultRegistrationValidator,
    CodeValidationPayloadSchema,
    CodeValidationPayload,
)


def process_command(command: types.Command, seq: str, repo: DialogRepository = None):
    if repo is None:
        repo = DynamoDBDialogRepository()
    dialog_state = repo.fetch_dialog_state(command.phone_number)
    command_seq = int(seq)
    state_seq = int(dialog_state.seq)
    if command_seq <= state_seq:
        logging.info(
            f"Processing already processed command {seq}. Current dialog state has "
            f"sequence {dialog_state.seq}."
        )
        return

    events = command.execute(dialog_state)
    for event in events:
        # deep copying the event so that modifications to the dialog_state don't have
        # side effects on the events that we're persisting. The user_profile on the event
        # should reflect the user_profile *before* the event is applied to the dialog_state.
        deepcopy(event).apply_to(dialog_state)
    dialog_state.seq = seq
    repo.persist_dialog_state(events, dialog_state)


class StartDrill(types.Command):
    def __init__(self, phone_number: str, drill: drills.Drill):
        super().__init__(phone_number)
        self.drill = drill

    def execute(self, dialog_state: types.DialogState) -> List[types.DialogEvent]:
        return [
            DrillStarted(
                self.phone_number, dialog_state.user_profile, self.drill, self.drill.first_prompt()
            )
        ]


class TriggerReminder(types.Command):
    def __init__(self, phone_number: str, drill_instance_id: uuid.UUID, prompt_slug: str):
        super().__init__(phone_number)
        self.prompt_slug = prompt_slug
        self.drill_instance_id = drill_instance_id

    def execute(self, dialog_state: types.DialogState) -> List[types.DialogEvent]:
        drill = dialog_state.current_drill
        if drill is None or dialog_state.drill_instance_id != self.drill_instance_id:
            return []

        prompt = dialog_state.current_prompt_state
        if prompt is None or prompt.slug != self.prompt_slug:
            return []

        if prompt.reminder_triggered:
            # to ensure idempotence
            return []

        return [ReminderTriggered(self.phone_number, dialog_state.user_profile)]


class ProcessSMSMessage(types.Command):
    def __init__(
        self,
        phone_number: str,
        content: str,
        registration_validator: Optional[RegistrationValidator] = None,
    ):
        super().__init__(phone_number)
        self.content = content.strip()
        self.content_lower = self.content.lower()
        if registration_validator is None:
            registration_validator = DefaultRegistrationValidator()
        self.registration_validator = registration_validator

    def execute(self, dialog_state: types.DialogState) -> List[types.DialogEvent]:
        if not dialog_state.user_profile.validated:
            validation_payload = self.registration_validator.validate_code(self.content_lower)
            if validation_payload.valid:
                return [
                    UserValidated(
                        phone_number=self.phone_number,
                        user_profile=dialog_state.user_profile,
                        code_validation_payload=validation_payload,
                    )
                ]
            return [UserValidationFailed(self.phone_number, dialog_state.user_profile)]

        prompt = dialog_state.get_prompt()
        if prompt is None:
            return []
        events = []
        if prompt.should_advance_with_answer(
            self.content_lower, dialog_state.user_profile.language
        ):
            events.append(
                CompletedPrompt(
                    phone_number=self.phone_number,
                    user_profile=dialog_state.user_profile,
                    prompt=prompt,
                    drill_instance_id=dialog_state.drill_instance_id,  # type: ignore
                    response=self.content,
                )
            )
            should_advance = True
        else:
            should_advance = dialog_state.current_prompt_state.failures >= prompt.max_failures
            events.append(
                FailedPrompt(
                    phone_number=self.phone_number,
                    user_profile=dialog_state.user_profile,
                    prompt=prompt,
                    response=self.content,
                    drill_instance_id=dialog_state.drill_instance_id,  # type: ignore
                    abandoned=should_advance,
                )
            )

        if should_advance:
            next_prompt = dialog_state.get_next_prompt()
            if next_prompt is not None:
                events.append(
                    AdvancedToNextPrompt(
                        phone_number=self.phone_number,
                        user_profile=dialog_state.user_profile,
                        prompt=next_prompt,
                        drill_instance_id=dialog_state.drill_instance_id,  # type: ignore
                    )
                )
                if dialog_state.is_next_prompt_last():
                    # assume the last prompt doesn't wait for an answer
                    events.append(
                        DrillCompleted(
                            self.phone_number,
                            dialog_state.user_profile,
                            dialog_state.drill_instance_id,  # type: ignore
                        )
                    )
        return events


class DrillStartedSchema(types.DialogEventSchema):
    drill = fields.Nested(drills.DrillSchema, required=True)
    drill_instance_id = fields.UUID(required=True)
    first_prompt = fields.Nested(drills.PromptSchema, required=True)

    @post_load
    def make_drill_started(self, data, **kwargs):
        return DrillStarted(**{k: v for k, v in data.items() if k != "event_type"})


class DrillStarted(types.DialogEvent):
    def __init__(
        self,
        phone_number: str,
        user_profile: types.UserProfile,
        drill: drills.Drill,
        first_prompt: drills.Prompt,
        **kwargs,
    ):
        super().__init__(
            DrillStartedSchema(),
            types.DialogEventType.DRILL_STARTED,
            phone_number,
            user_profile,
            **kwargs,
        )
        self.drill = drill
        self.first_prompt = first_prompt
        self.drill_instance_id = kwargs.get("drill_instance_id", uuid.uuid4())

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.current_drill = self.drill
        dialog_state.drill_instance_id = self.drill_instance_id
        dialog_state.current_prompt_state = types.PromptState(
            self.first_prompt.slug, start_time=self.created_time
        )


class ReminderTriggeredSchema(types.DialogEventSchema):
    @post_load
    def make_reminder_triggered(self, data, **kwargs):
        return ReminderTriggered(**{k: v for k, v in data.items() if k != "event_type"})


class ReminderTriggered(types.DialogEvent):
    def __init__(self, phone_number: str, user_profile: types.UserProfile, **kwargs):
        super().__init__(
            ReminderTriggeredSchema(),
            types.DialogEventType.REMINDER_TRIGGERED,
            phone_number,
            user_profile,
            **kwargs,
        )

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.current_prompt_state.reminder_triggered = True


class UserValidatedSchema(types.DialogEventSchema):
    code_validation_payload = fields.Nested(CodeValidationPayloadSchema, required=True)

    @post_load
    def make_user_created(self, data, **kwargs):
        return UserValidated(**{k: v for k, v in data.items() if k != "event_type"})


class UserValidated(types.DialogEvent):
    def __init__(
        self,
        phone_number: str,
        user_profile: types.UserProfile,
        code_validation_payload: CodeValidationPayload,
        **kwargs,
    ):
        super().__init__(
            UserValidatedSchema(),
            types.DialogEventType.USER_VALIDATED,
            phone_number,
            user_profile,
            **kwargs,
        )
        self.code_validation_payload = code_validation_payload

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.user_profile.validated = True
        dialog_state.user_profile.is_demo = self.code_validation_payload.is_demo
        dialog_state.user_profile.account_info = self.code_validation_payload.account_info


class UserValidationFailedSchema(types.DialogEventSchema):
    @post_load
    def make_user_creation_failed(self, data, **kwargs):
        return UserValidationFailed(**{k: v for k, v in data.items() if k != "event_type"})


class UserValidationFailed(types.DialogEvent):
    def __init__(self, phone_number: str, user_profile: types.UserProfile, **kwargs):
        super().__init__(
            UserValidationFailedSchema(),
            types.DialogEventType.USER_VALIDATION_FAILED,
            phone_number,
            user_profile,
            **kwargs,
        )

    def apply_to(self, dialog_state: types.DialogState):
        pass


class CompletedPromptSchema(types.DialogEventSchema):
    prompt = fields.Nested(drills.PromptSchema, required=True)
    response = fields.String(required=True)
    drill_instance_id = fields.UUID(required=True)

    @post_load
    def make_completed_prompt(self, data, **kwargs):
        return CompletedPrompt(**{k: v for k, v in data.items() if k != "event_type"})


class CompletedPrompt(types.DialogEvent):
    def __init__(
        self,
        phone_number: str,
        user_profile: types.UserProfile,
        prompt: drills.Prompt,
        drill_instance_id: uuid.UUID,
        response: str,
        **kwargs,
    ):
        super().__init__(
            CompletedPromptSchema(),
            types.DialogEventType.COMPLETED_PROMPT,
            phone_number,
            user_profile,
            **kwargs,
        )
        self.prompt = prompt
        self.response = response
        self.drill_instance_id = drill_instance_id

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.current_prompt_state = None
        if self.prompt.response_user_profile_key:
            setattr(dialog_state.user_profile, self.prompt.response_user_profile_key, self.response)


class FailedPromptSchema(types.DialogEventSchema):
    prompt = fields.Nested(drills.PromptSchema, required=True)
    abandoned = fields.Boolean(required=True)
    response = fields.String(required=True)
    drill_instance_id = fields.UUID(required=True)

    @post_load
    def make_failed_prompt(self, data, **kwargs):
        return FailedPrompt(**{k: v for k, v in data.items() if k != "event_type"})


class FailedPrompt(types.DialogEvent):
    def __init__(
        self,
        phone_number: str,
        user_profile: types.UserProfile,
        prompt: drills.Prompt,
        drill_instance_id: uuid.UUID,
        response: str,
        abandoned: bool,
        **kwargs,
    ):
        super().__init__(
            FailedPromptSchema(),
            types.DialogEventType.FAILED_PROMPT,
            phone_number,
            user_profile,
            **kwargs,
        )
        self.prompt = prompt
        self.abandoned = abandoned
        self.response = response
        self.drill_instance_id = drill_instance_id

    def apply_to(self, dialog_state: types.DialogState):
        if self.abandoned:
            dialog_state.current_prompt_state = None
        else:
            dialog_state.current_prompt_state.failures += 1


class AdvancedToNextPromptSchema(types.DialogEventSchema):
    prompt = fields.Nested(drills.PromptSchema, required=True)
    drill_instance_id = fields.UUID(required=True)

    @post_load
    def make_advanced_to_next_prompt(self, data, **kwargs):
        return AdvancedToNextPrompt(**{k: v for k, v in data.items() if k != "event_type"})


class AdvancedToNextPrompt(types.DialogEvent):
    def __init__(
        self,
        phone_number: str,
        user_profile: types.UserProfile,
        prompt: drills.Prompt,
        drill_instance_id: uuid.UUID,
        **kwargs,
    ):
        super().__init__(
            AdvancedToNextPromptSchema(),
            types.DialogEventType.ADVANCED_TO_NEXT_PROMPT,
            phone_number,
            user_profile,
            **kwargs,
        )
        self.prompt = prompt
        self.drill_instance_id = drill_instance_id

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.current_prompt_state = types.PromptState(
            self.prompt.slug, start_time=self.created_time
        )


class DrillCompletedSchema(types.DialogEventSchema):
    drill_instance_id = fields.UUID(required=True)

    @post_load
    def make_drill_completed(self, data, **kwargs):
        return DrillCompleted(**{k: v for k, v in data.items() if k != "event_type"})


class DrillCompleted(types.DialogEvent):
    def __init__(
        self,
        phone_number: str,
        user_profile: types.UserProfile,
        drill_instance_id: uuid.UUID,
        **kwargs,
    ):
        super().__init__(
            DrillCompletedSchema(),
            types.DialogEventType.DRILL_COMPLETED,
            phone_number,
            user_profile,
            **kwargs,
        )
        self.drill_instance_id = drill_instance_id

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.current_drill = None
        dialog_state.drill_instance_id = None


def event_from_dict(event_dict: Dict[str, Any]) -> types.DialogEvent:
    event_type = types.DialogEventType[event_dict["event_type"]]
    if event_type == types.DialogEventType.ADVANCED_TO_NEXT_PROMPT:
        return AdvancedToNextPromptSchema().load(event_dict)
    if event_type == types.DialogEventType.DRILL_COMPLETED:
        return DrillCompletedSchema().load(event_dict)
    if event_type == types.DialogEventType.USER_VALIDATION_FAILED:
        return UserValidationFailedSchema().load(event_dict)
    if event_type == types.DialogEventType.DRILL_STARTED:
        return DrillStartedSchema().load(event_dict)
    if event_type == types.DialogEventType.USER_VALIDATED:
        return UserValidatedSchema().load(event_dict)
    if event_type == types.DialogEventType.COMPLETED_PROMPT:
        return CompletedPromptSchema().load(event_dict)
    if event_type == types.DialogEventType.FAILED_PROMPT:
        return FailedPromptSchema().load(event_dict)
    if event_type == types.DialogEventType.REMINDER_TRIGGERED:
        return ReminderTriggeredSchema().load(event_dict)
    raise ValueError(f"unknown event type {event_type}")
