import unittest
import uuid
from typing import List

from stopcovid.drills.localize import localize
from stopcovid.event_distributor.outbound_sms import (
    get_outbound_sms_commands,
    USER_VALIDATION_FAILED_COPY,
    CORRECT_ANSWER_COPY,
)
from stopcovid.dialog.types import UserProfileSchema, DialogEvent
from stopcovid.dialog.dialog import (
    UserValidationFailed,
    UserValidated,
    DrillCompleted,
    DrillStarted,
    CompletedPrompt,
    FailedPrompt,
    AdvancedToNextPrompt,
)
from stopcovid.drills.drills import Drill, Prompt, PromptMessage
from stopcovid.dialog.registration import CodeValidationPayload


class TestHandleCommand(unittest.TestCase):
    def setUp(self):
        self.phone = "+15554238324"
        self.validated_user_profile = UserProfileSchema().load(
            {"validated": True, "language": "en", "name": "Mario", "is_demo": False}
        )
        self.non_validated_user_profile = UserProfileSchema().load(
            {"validated": False, "language": "en", "name": "Luigi", "is_demo": False}
        )

        self.drill = Drill(
            name="Test Drill",
            slug="test-drill",
            prompts=[
                Prompt(slug="ignore-response-1", messages=[PromptMessage(text="Hello")]),
                Prompt(
                    slug="graded-response-1",
                    messages=[PromptMessage(text="Intro!"), PromptMessage(text="Question 1")],
                    correct_response="a",
                ),
                Prompt(
                    slug="graded-response-2",
                    messages=[PromptMessage(text="Question 2")],
                    correct_response="b",
                ),
            ],
        )

    def test_user_validation_failed_event(self):
        dialog_events: List[DialogEvent] = [
            UserValidationFailed(self.phone, self.non_validated_user_profile)
        ]
        outbound_messages = get_outbound_sms_commands(dialog_events)
        self.assertEqual(len(outbound_messages), 1)
        message = outbound_messages[0]
        self.assertEqual(message.phone_number, self.phone)
        self.assertEqual(message.event_id, dialog_events[0].event_id)
        self.assertEqual(message.body, USER_VALIDATION_FAILED_COPY)

    def test_user_validated_event(self):
        code_validation_payload = CodeValidationPayload(valid=True, is_demo=False)
        dialog_events: List[DialogEvent] = [
            UserValidated(self.phone, self.validated_user_profile, code_validation_payload)
        ]
        outbound_messages = get_outbound_sms_commands(dialog_events)
        self.assertEqual(len(outbound_messages), 0)

    def test_drill_completed_event(self):
        dialog_events: List[DialogEvent] = [
            DrillCompleted(self.phone, self.validated_user_profile, drill_instance_id=uuid.uuid4())
        ]
        outbound_messages = get_outbound_sms_commands(dialog_events)
        self.assertEqual(len(outbound_messages), 0)

    def test_drill_started_event(self):
        dialog_events: List[DialogEvent] = [
            DrillStarted(
                self.phone,
                self.validated_user_profile,
                drill=self.drill,
                first_prompt=self.drill.prompts[0],
            )
        ]
        outbound_messages = get_outbound_sms_commands(dialog_events)
        self.assertEqual(len(outbound_messages), 1)
        message = outbound_messages[0]
        self.assertEqual(message.phone_number, self.phone)
        self.assertEqual(message.event_id, dialog_events[0].event_id)
        self.assertEqual(message.body, "Hello")

    def test_completed_prompt_event(self):
        dialog_events: List[DialogEvent] = [
            CompletedPrompt(
                self.phone,
                self.validated_user_profile,
                prompt=self.drill.prompts[1],
                response="a",
                drill_instance_id=uuid.uuid4(),
            )
        ]
        outbound_messages = get_outbound_sms_commands(dialog_events)
        self.assertEqual(len(outbound_messages), 1)
        message = outbound_messages[0]
        self.assertEqual(message.phone_number, self.phone)
        self.assertEqual(message.event_id, dialog_events[0].event_id)
        self.assertEqual(message.body, localize(CORRECT_ANSWER_COPY, "en", emojis=""))

    def test_abandoned_failed_prompt_event(self):

        dialog_events: List[DialogEvent] = [
            FailedPrompt(
                self.phone,
                self.validated_user_profile,
                prompt=self.drill.prompts[1],
                response="a",
                drill_instance_id=uuid.uuid4(),
                abandoned=True,
            )
        ]
        outbound_messages = get_outbound_sms_commands(dialog_events)
        self.assertEqual(len(outbound_messages), 1)
        message = outbound_messages[0]
        self.assertEqual(message.phone_number, self.phone)
        self.assertEqual(message.event_id, dialog_events[0].event_id)
        self.assertEqual(message.body, "🤖 The correct answer is *a*.\n\nLets move to the next one.")

    def test_non_abandoned_failed_prompt_event(self):
        dialog_events: List[DialogEvent] = [
            FailedPrompt(
                self.phone,
                self.validated_user_profile,
                prompt=self.drill.prompts[1],
                response="a",
                drill_instance_id=uuid.uuid4(),
                abandoned=False,
            )
        ]
        outbound_messages = get_outbound_sms_commands(dialog_events)
        self.assertEqual(len(outbound_messages), 1)
        message = outbound_messages[0]
        self.assertEqual(message.phone_number, self.phone)
        self.assertEqual(message.event_id, dialog_events[0].event_id)
        self.assertEqual(message.body, "🤖 Sorry, not correct. 🤔\n\n*Try again one more time!*")

    def test_advance_to_next_prompt_event(self):
        dialog_events: List[DialogEvent] = [
            AdvancedToNextPrompt(
                self.phone,
                self.validated_user_profile,
                prompt=self.drill.prompts[1],
                drill_instance_id=uuid.uuid4(),
            )
        ]
        outbound_messages = get_outbound_sms_commands(dialog_events)
        self.assertEqual(len(outbound_messages), 2)
        expected_messages = [message.text for message in self.drill.prompts[1].messages]

        self.assertEqual(outbound_messages[0].phone_number, self.phone)
        self.assertEqual(outbound_messages[0].event_id, dialog_events[0].event_id)
        self.assertEqual(outbound_messages[0].body, expected_messages[0])

        self.assertEqual(outbound_messages[1].phone_number, self.phone)
        self.assertEqual(outbound_messages[1].event_id, dialog_events[0].event_id)
        self.assertEqual(outbound_messages[1].body, expected_messages[1])
