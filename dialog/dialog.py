import uuid
from typing import List

from drills import drills
from .persistence import DialogRepository, DynamoDBDialogRepository
from .types import Command, DialogState, DialogEvent, DialogEventType, PromptState

VALID_OPT_IN_CODES = {"drill0"}


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
            if next_prompt is not None:
                events.append(AdvancedToNextPrompt(self.phone_number, next_prompt))
                if dialog_state.is_next_prompt_last():
                    # assume the last prompt doesn't wait for an answer
                    events.append(DrillCompleted(self.phone_number, dialog_state.current_drill))
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
