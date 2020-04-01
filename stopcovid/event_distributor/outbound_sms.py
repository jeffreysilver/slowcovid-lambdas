import logging
from typing import List
from dataclasses import dataclass

from stopcovid.dialog.types import DialogEvent
from stopcovid.dialog.dialog import (
    DrillCompleted,
    AdvancedToNextPrompt,
    FailedPrompt,
    CompletedPrompt,
    UserValidated,
    DrillStarted,
    UserValidationFailed,
)
from stopcovid.drills.localize import localize


TRY_AGAIN = "{{incorrect_answer}}"

USER_VALIDATION_FAILED_COPY = (
    "Invalid Code. Check with your administrator and make sure you have the right code."
)

# We should template these for localization
CORRECT_ANSWER_COPY = "Correct!"

DELAY_BETWEEN_MESSAGE_IN_SECONDS = 3


@dataclass
class OutboundSMS:
    event_id: str
    phone_number: str
    body: str
    delay_seconds: int


def get_localized_messages(
    dialog_event: DialogEvent, messages: List[str], with_initial_pause: bool = False, **kwargs
) -> List[OutboundSMS]:
    language = dialog_event.user_profile.language

    initial_pause_seconds = DELAY_BETWEEN_MESSAGE_IN_SECONDS if with_initial_pause else 0

    return [
        OutboundSMS(
            event_id=dialog_event.event_id,
            phone_number=dialog_event.phone_number,
            body=localize(message, language, **kwargs),
            delay_seconds=initial_pause_seconds + (i * DELAY_BETWEEN_MESSAGE_IN_SECONDS),
        )
        for i, message in enumerate(messages)
    ]


def get_messages_for_command(event: DialogEvent):  # noqa: C901
    if isinstance(event, AdvancedToNextPrompt):
        return get_localized_messages(event, event.prompt.messages, with_initial_pause=True)

    elif isinstance(event, FailedPrompt):
        if not event.abandoned:
            return get_localized_messages(event, [TRY_AGAIN])
        elif event.prompt.correct_response:
            return get_localized_messages(
                event,
                ["{{corrected_answer}}"],
                correct_answer=localize(event.prompt.correct_response, event.user_profile.language),
            )

    elif isinstance(event, CompletedPrompt):
        if event.prompt.correct_response is not None:
            return get_localized_messages(event, [CORRECT_ANSWER_COPY])

    elif isinstance(event, UserValidated):
        # User validated events will cause the scheduler to kick off a drill
        pass

    elif isinstance(event, UserValidationFailed):
        return get_localized_messages(event, [USER_VALIDATION_FAILED_COPY])

    elif isinstance(event, DrillStarted):
        return get_localized_messages(event, event.first_prompt.messages)

    elif isinstance(event, DrillCompleted):
        # Drills include a drill completed message
        pass

    else:
        logging.info(f"Unknown event type: {event.event_type}")

    return []


def get_outbound_sms_commands(dialog_events: List[DialogEvent]) -> List[OutboundSMS]:
    outbound_messages = []

    for event in dialog_events:
        outbound_messages.extend(get_messages_for_command(event))

    return outbound_messages


def distribute_outbound_sms_events(dialog_events: List[DialogEvent]):
    from stopcovid.clients import sqs

    outbound_messages = get_outbound_sms_commands(dialog_events)
    sqs.publish_outbound_sms_messages(outbound_messages)
