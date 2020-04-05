import logging
import uuid
from copy import deepcopy
from typing import List, Dict, Any, Optional, Type

from marshmallow import fields, post_load, utils

from stopcovid.drills import drills
from .persistence import DialogRepository, DynamoDBDialogRepository
from . import types
from .registration import (
    RegistrationValidator,
    DefaultRegistrationValidator,
    CodeValidationPayloadSchema,
    CodeValidationPayload,
)
from .types import DialogEventBatch, DialogState

DEFAULT_REGISTRATION_VALIDATOR = DefaultRegistrationValidator()


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
    repo.persist_dialog_state(
        DialogEventBatch(events=events, phone_number=command.phone_number, seq=seq), dialog_state
    )


class StartDrill(types.Command):
    def __init__(self, phone_number: str, drill: drills.Drill):
        super().__init__(phone_number)
        self.drill = drill

    def execute(self, dialog_state: types.DialogState) -> List[types.DialogEvent]:
        return [
            DrillStarted(
                phone_number=self.phone_number,
                user_profile=dialog_state.user_profile,
                drill=self.drill,
                first_prompt=self.drill.first_prompt(),
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
            registration_validator = DEFAULT_REGISTRATION_VALIDATOR
        self.registration_validator = registration_validator

    def execute(self, dialog_state: types.DialogState) -> List[types.DialogEvent]:
        base_args = {"phone_number": self.phone_number, "user_profile": dialog_state.user_profile}

        # a chain of responsibility. Each handler can handle the current command and return an
        # event list. A handler can also NOT handle an event and return None, thereby leaving it
        # for the next handler.
        for handler in [
            self._respond_to_help,
            self._handle_opt_out,
            self._handle_opt_back_in,
            self._validate_registration,
            self._check_response,
            self._advance_to_next_drill,
        ]:
            result = handler(dialog_state, base_args)
            if result is not None:
                return result
        return []

    def _respond_to_help(
        self, dialog_state: types.DialogState, base_args: Dict[str, Any]
    ) -> Optional[List[types.DialogEvent]]:
        if self.content_lower == "help":
            # Twilio will respond with help text
            return []

    def _handle_opt_out(
        self, dialog_state: types.DialogState, base_args: Dict[str, Any]
    ) -> Optional[List[types.DialogEvent]]:
        if self.content_lower in ["cancel", "end", "quit", "stop", "stopall", "unsubscribe"]:
            return [OptedOut(drill_instance_id=dialog_state.drill_instance_id, **base_args)]

    def _handle_opt_back_in(
        self, dialog_state: types.DialogState, base_args: Dict[str, Any]
    ) -> Optional[List[types.DialogEvent]]:
        if dialog_state.user_profile.opted_out:
            if self.content_lower == "start":
                return [NextDrillRequested(**base_args)]
            return []

    def _validate_registration(
        self, dialog_state: types.DialogState, base_args: Dict[str, Any]
    ) -> Optional[List[types.DialogEvent]]:

        if dialog_state.user_profile.is_demo or not dialog_state.user_profile.validated:
            validation_payload = self.registration_validator.validate_code(self.content_lower)
            if validation_payload.valid:
                return [UserValidated(code_validation_payload=validation_payload, **base_args)]
            if not dialog_state.user_profile.validated:
                return [UserValidationFailed(**base_args)]

    def _check_response(
        self, dialog_state: types.DialogState, base_args: Dict[str, Any]
    ) -> Optional[List[types.DialogEvent]]:
        prompt = dialog_state.get_prompt()
        if prompt is None:
            return
        events = []
        if prompt.should_advance_with_answer(
            self.content_lower, dialog_state.user_profile.language
        ):
            events.append(
                CompletedPrompt(
                    prompt=prompt,
                    drill_instance_id=dialog_state.drill_instance_id,  # type: ignore
                    response=self.content,
                    **base_args,
                )
            )
            should_advance = True
        else:
            should_advance = dialog_state.current_prompt_state.failures >= prompt.max_failures
            events.append(
                FailedPrompt(
                    prompt=prompt,
                    response=self.content,
                    drill_instance_id=dialog_state.drill_instance_id,  # type: ignore
                    abandoned=should_advance,
                    **base_args,
                )
            )

        if should_advance:
            next_prompt = dialog_state.get_next_prompt()
            if next_prompt is not None:
                events.append(
                    AdvancedToNextPrompt(
                        prompt=next_prompt,
                        drill_instance_id=dialog_state.drill_instance_id,  # type: ignore
                        **base_args,
                    )
                )
                if dialog_state.is_next_prompt_last():
                    # assume the last prompt doesn't wait for an answer
                    events.append(
                        DrillCompleted(
                            drill_instance_id=dialog_state.drill_instance_id,  # type: ignore
                            **base_args,
                        )
                    )
        return events

    def _advance_to_next_drill(
        self, dialog_state: types.DialogState, base_args: Dict[str, Any]
    ) -> Optional[List[types.DialogEvent]]:
        prompt = dialog_state.get_prompt()
        if prompt is None:
            if self.content_lower == "more":
                return [NextDrillRequested(**base_args)]
            return []


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
        dialog_state.drill_instance_id = None
        dialog_state.current_prompt_state = None
        dialog_state.current_drill = None
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
            dialog_state.current_prompt_state.last_response_time = self.created_time
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
        dialog_state.current_prompt_state = None


class OptedOutSchema(types.DialogEventSchema):
    drill_instance_id = fields.UUID()

    @post_load
    def make_opted_out(self, data, **kwargs):
        return OptedOut(**{k: v for k, v in data.items() if k != "event_type"})


class OptedOut(types.DialogEvent):
    def __init__(
        self,
        phone_number: str,
        user_profile: types.UserProfile,
        drill_instance_id: Optional[uuid.UUID],
        **kwargs,
    ):
        super().__init__(
            OptedOutSchema(), types.DialogEventType.OPTED_OUT, phone_number, user_profile, **kwargs
        )
        self.drill_instance_id = drill_instance_id

    def apply_to(self, dialog_state: DialogState):
        dialog_state.drill_instance_id = None
        dialog_state.user_profile.opted_out = True
        dialog_state.current_drill = None
        dialog_state.current_prompt_state = None


class NextDrillRequestedSchema(types.DialogEventSchema):
    @post_load
    def make_next_drill_requested(self, data, **kwargs):
        return NextDrillRequested(**{k: v for k, v in data.items() if k != "event_type"})


class NextDrillRequested(types.DialogEvent):
    def __init__(self, phone_number: str, user_profile: types.UserProfile, **kwargs):
        super().__init__(
            NextDrillRequestedSchema(),
            types.DialogEventType.NEXT_DRILL_REQUESTED,
            phone_number,
            user_profile,
            **kwargs,
        )

    def apply_to(self, dialog_state: DialogState):
        dialog_state.user_profile.opted_out = False


TYPE_TO_SCHEMA: Dict[types.DialogEventType, Type[types.DialogEventSchema]] = {
    types.DialogEventType.ADVANCED_TO_NEXT_PROMPT: AdvancedToNextPromptSchema,
    types.DialogEventType.DRILL_COMPLETED: DrillCompletedSchema,
    types.DialogEventType.USER_VALIDATION_FAILED: UserValidationFailedSchema,
    types.DialogEventType.DRILL_STARTED: DrillStartedSchema,
    types.DialogEventType.USER_VALIDATED: UserValidatedSchema,
    types.DialogEventType.COMPLETED_PROMPT: CompletedPromptSchema,
    types.DialogEventType.FAILED_PROMPT: FailedPromptSchema,
    types.DialogEventType.REMINDER_TRIGGERED: ReminderTriggeredSchema,
    types.DialogEventType.OPTED_OUT: OptedOutSchema,
    types.DialogEventType.NEXT_DRILL_REQUESTED: NextDrillRequestedSchema,
}


def event_from_dict(event_dict: Dict[str, Any]) -> types.DialogEvent:
    event_type = types.DialogEventType[event_dict["event_type"]]
    return TYPE_TO_SCHEMA[event_type]().load(event_dict)


def batch_from_dict(batch_dict: Dict[str, Any]) -> types.DialogEventBatch:
    return DialogEventBatch(
        batch_id=uuid.UUID(batch_dict["batch_id"]),
        phone_number=batch_dict["phone_number"],
        seq=batch_dict["seq"],
        created_time=utils.from_iso_datetime(batch_dict["created_time"]),
        events=[event_from_dict(event_dict) for event_dict in batch_dict["events"]],
    )
