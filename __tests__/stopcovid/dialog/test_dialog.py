import datetime
import unittest
import uuid
from typing import List

from unittest.mock import MagicMock, patch, Mock

from stopcovid.dialog.registration import CodeValidationPayload
from stopcovid.drills.drills import Prompt, Drill
from stopcovid.dialog.dialog import (
    process_command,
    ProcessSMSMessage,
    StartDrill,
    CompletedPrompt,
    AdvancedToNextPrompt,
    FailedPrompt,
    DrillCompleted,
    TriggerReminder,
    event_from_dict,
    DrillStarted,
    ReminderTriggered,
    UserValidationFailed,
    UserValidated,
)
from stopcovid.dialog.types import (
    DialogEvent,
    UserProfile,
    DialogState,
    DialogEventType,
    PromptState,
)

DRILL = Drill(
    name="test-drill",
    prompts=[
        Prompt(slug="ignore-response-1", messages=["{{msg1}}"]),
        Prompt(
            slug="store-response", messages=["{{msg1}}"], response_user_profile_key="self_rating_1"
        ),
        Prompt(slug="graded-response-1", messages=["{{msg1}}"], correct_response="{{response1}}"),
        Prompt(slug="graded-response-2", messages=["{{msg1}}"], correct_response="{{response1}}"),
        Prompt(slug="ignore-response-2", messages=["{{msg1}}"]),
    ],
)


class TestDialogFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.phone_number = "123456789"
        self.dialog_state = DialogState(phone_number=self.phone_number, seq="0")
        self.drill = DRILL
        self.repo = MagicMock()
        self.repo.fetch_dialog_state = MagicMock(return_value=self.dialog_state)
        self.repo.persist_dialog_state = MagicMock()
        self.next_seq = 1
        self.current_correct_response = "translated"  # produced by the mock localize method
        self.now = datetime.datetime.now(datetime.timezone.utc)
        self.localization_patcher = patch(
            "stopcovid.drills.drills.localize", return_value="translated"
        )
        self.localization_patcher.start()

    def tearDown(self) -> None:
        self.localization_patcher.stop()

    def _process_command(self, command):
        process_command(command, str(self.next_seq), repo=self.repo)
        self.next_seq += 1
        self.repo.persist_dialog_state.assert_called_once()
        return self.repo.persist_dialog_state.call_args[0][0]

    def _assert_event_types(self, events: List[DialogEvent], *args: DialogEventType):
        self.assertEqual(len(args), len(events))
        for i in range(len(events)):
            self.assertEqual(args[i], events[i].event_type)

    def _set_current_prompt(self, prompt_index: int):
        self.dialog_state.current_drill = self.drill
        prompt = self.drill.prompts[prompt_index]
        self.dialog_state.current_prompt_state = PromptState(slug=prompt.slug, start_time=self.now)

    def test_skip_processed_sequence_numbers(self):
        command = Mock(wraps=ProcessSMSMessage(self.phone_number, "hey"))
        process_command(command, "0", repo=self.repo)
        self.assertFalse(command.execute.called)

    def test_first_message_validates_user(self):
        validator = MagicMock()
        validation_payload = CodeValidationPayload(valid=True, account_info={"company": "WeWork"})
        validator.validate_code = MagicMock(return_value=validation_payload)
        command = ProcessSMSMessage(self.phone_number, "hey", registration_validator=validator)
        self.assertFalse(self.dialog_state.user_profile.validated)

        events = self._process_command(command)

        self._assert_event_types(events, DialogEventType.USER_VALIDATED)
        self.assertTrue(self.dialog_state.user_profile.validated)
        self.assertEqual(validation_payload, events[0].code_validation_payload)

    def test_first_message_does_not_validate_user(self):
        validator = MagicMock()
        validation_payload = CodeValidationPayload(valid=False)
        validator.validate_code = MagicMock(return_value=validation_payload)
        command = ProcessSMSMessage(self.phone_number, "hey", registration_validator=validator)
        self.assertFalse(self.dialog_state.user_profile.validated)

        events = self._process_command(command)

        self._assert_event_types(events, DialogEventType.USER_VALIDATION_FAILED)
        self.assertFalse(self.dialog_state.user_profile.validated)

    def test_start_drill(self):
        self.dialog_state.user_profile.validated = True
        command = StartDrill(self.phone_number, self.drill)

        events = self._process_command(command)

        self._assert_event_types(events, DialogEventType.DRILL_STARTED)
        self.assertEqual(self.drill, events[0].drill)
        self.assertEqual(self.drill.first_prompt(), events[0].first_prompt)
        self.assertIsNotNone(events[0].drill_instance_id)

        self.assertEqual(self.drill, self.dialog_state.current_drill)
        self.assertEqual(
            PromptState(
                slug=self.drill.first_prompt().slug,
                start_time=events[0].created_time,
                reminder_triggered=False,
                failures=0,
            ),
            self.dialog_state.current_prompt_state,
        )
        self.assertEqual(events[0].drill_instance_id, self.dialog_state.drill_instance_id)

    def test_advance_ignore(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(0)
        command = ProcessSMSMessage(self.phone_number, "go")
        events = self._process_command(command)
        self._assert_event_types(
            events, DialogEventType.COMPLETED_PROMPT, DialogEventType.ADVANCED_TO_NEXT_PROMPT
        )
        completed_event: CompletedPrompt = events[0]
        self.assertEqual(completed_event.prompt, self.drill.prompts[0])
        self.assertEqual(completed_event.response, "go")
        self.assertEqual(completed_event.drill_instance_id, self.dialog_state.drill_instance_id)

        advanced_event: AdvancedToNextPrompt = events[1]
        self.assertEqual(self.drill.prompts[1], advanced_event.prompt)
        self.assertEqual(self.dialog_state.drill_instance_id, advanced_event.drill_instance_id)

        self.assertEqual(
            PromptState(
                slug=self.drill.prompts[1].slug,
                start_time=advanced_event.created_time,
                reminder_triggered=False,
                failures=0,
            ),
            self.dialog_state.current_prompt_state,
        )

    def test_advance_store_value(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(1)
        command = ProcessSMSMessage(self.phone_number, "7")
        events = self._process_command(command)
        self._assert_event_types(
            events, DialogEventType.COMPLETED_PROMPT, DialogEventType.ADVANCED_TO_NEXT_PROMPT
        )
        completed_event: CompletedPrompt = events[0]
        self.assertEqual(completed_event.prompt, self.drill.prompts[1])
        self.assertEqual(completed_event.response, "7")
        self.assertEqual(completed_event.drill_instance_id, self.dialog_state.drill_instance_id)

        advanced_event: AdvancedToNextPrompt = events[1]
        self.assertEqual(self.drill.prompts[2], advanced_event.prompt)
        self.assertEqual(self.dialog_state.drill_instance_id, advanced_event.drill_instance_id)

        self.assertEqual(
            PromptState(
                slug=self.drill.prompts[2].slug,
                start_time=advanced_event.created_time,
                reminder_triggered=False,
                failures=0,
            ),
            self.dialog_state.current_prompt_state,
        )
        self.assertEqual("7", self.dialog_state.user_profile.self_rating_1)

    def test_advance_graded_with_right_answer(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(2)
        command = ProcessSMSMessage(self.phone_number, self.current_correct_response)
        events = self._process_command(command)
        self._assert_event_types(
            events, DialogEventType.COMPLETED_PROMPT, DialogEventType.ADVANCED_TO_NEXT_PROMPT
        )
        completed_event: CompletedPrompt = events[0]
        self.assertEqual(completed_event.prompt, self.drill.prompts[2])
        self.assertEqual(completed_event.response, self.current_correct_response)
        self.assertEqual(completed_event.drill_instance_id, self.dialog_state.drill_instance_id)

        advanced_event: AdvancedToNextPrompt = events[1]
        self.assertEqual(self.drill.prompts[3], advanced_event.prompt)
        self.assertEqual(self.dialog_state.drill_instance_id, advanced_event.drill_instance_id)

        self.assertEqual(
            PromptState(
                slug=self.drill.prompts[3].slug,
                start_time=advanced_event.created_time,
                reminder_triggered=False,
                failures=0,
            ),
            self.dialog_state.current_prompt_state,
        )

    def test_repeat_with_wrong_answer(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(2)
        command = ProcessSMSMessage(self.phone_number, "completely wrong answer")
        events = self._process_command(command)
        self._assert_event_types(events, DialogEventType.FAILED_PROMPT)
        failed_event: FailedPrompt = events[0]
        self.assertEqual(failed_event.prompt, self.drill.prompts[2])
        self.assertFalse(failed_event.abandoned)
        self.assertEqual(failed_event.response, "completely wrong answer")
        self.assertEqual(failed_event.drill_instance_id, self.dialog_state.drill_instance_id)

        self.assertEqual(
            PromptState(
                slug=self.drill.prompts[2].slug,
                start_time=self.now,
                last_response_time=failed_event.created_time,
                reminder_triggered=False,
                failures=1,
            ),
            self.dialog_state.current_prompt_state,
        )

    def test_advance_with_too_many_wrong_answers(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(2)
        self.dialog_state.current_prompt_state.failures = 1

        command = ProcessSMSMessage(self.phone_number, "completely wrong answer")
        events = self._process_command(command)
        self._assert_event_types(
            events, DialogEventType.FAILED_PROMPT, DialogEventType.ADVANCED_TO_NEXT_PROMPT
        )

        failed_event: FailedPrompt = events[0]
        self.assertEqual(failed_event.prompt, self.drill.prompts[2])
        self.assertTrue(failed_event.abandoned)
        self.assertEqual(failed_event.response, "completely wrong answer")
        self.assertEqual(failed_event.drill_instance_id, self.dialog_state.drill_instance_id)

        advanced_event: AdvancedToNextPrompt = events[1]
        self.assertEqual(self.drill.prompts[3], advanced_event.prompt)
        self.assertEqual(self.dialog_state.drill_instance_id, advanced_event.drill_instance_id)

        self.assertEqual(
            PromptState(
                slug=self.drill.prompts[3].slug,
                start_time=advanced_event.created_time,
                reminder_triggered=False,
                failures=0,
            ),
            self.dialog_state.current_prompt_state,
        )

    def test_conclude_with_right_answer(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(3)
        command = ProcessSMSMessage(self.phone_number, self.current_correct_response)
        events = self._process_command(command)
        self._assert_event_types(
            events,
            DialogEventType.COMPLETED_PROMPT,
            DialogEventType.ADVANCED_TO_NEXT_PROMPT,
            DialogEventType.DRILL_COMPLETED,
        )
        completed_event: CompletedPrompt = events[0]
        self.assertEqual(completed_event.prompt, self.drill.prompts[3])
        self.assertEqual(completed_event.response, self.current_correct_response)
        self.assertEqual(completed_event.drill_instance_id, self.dialog_state.drill_instance_id)

        advanced_event: AdvancedToNextPrompt = events[1]
        self.assertEqual(self.drill.prompts[4], advanced_event.prompt)
        self.assertEqual(self.dialog_state.drill_instance_id, advanced_event.drill_instance_id)

        drill_completed_event: DrillCompleted = events[2]
        self.assertEqual(
            self.dialog_state.drill_instance_id, drill_completed_event.drill_instance_id
        )

        self.assertIsNone(self.dialog_state.current_drill)
        self.assertIsNone(self.dialog_state.drill_instance_id)
        self.assertIsNone(self.dialog_state.current_prompt_state)

    def test_concude_with_too_many_wrong_answers(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(3)
        self.dialog_state.current_prompt_state.failures = 1

        command = ProcessSMSMessage(self.phone_number, "completely wrong answer")
        events = self._process_command(command)
        self._assert_event_types(
            events,
            DialogEventType.FAILED_PROMPT,
            DialogEventType.ADVANCED_TO_NEXT_PROMPT,
            DialogEventType.DRILL_COMPLETED,
        )

        failed_event: FailedPrompt = events[0]
        self.assertEqual(failed_event.prompt, self.drill.prompts[3])
        self.assertTrue(failed_event.abandoned)
        self.assertEqual(failed_event.response, "completely wrong answer")
        self.assertEqual(failed_event.drill_instance_id, self.dialog_state.drill_instance_id)

        advanced_event: AdvancedToNextPrompt = events[1]
        self.assertEqual(self.drill.prompts[4], advanced_event.prompt)
        self.assertEqual(self.dialog_state.drill_instance_id, advanced_event.drill_instance_id)

        drill_completed_event: DrillCompleted = events[2]
        self.assertEqual(
            self.dialog_state.drill_instance_id, drill_completed_event.drill_instance_id
        )

        self.assertIsNone(self.dialog_state.current_drill)
        self.assertIsNone(self.dialog_state.drill_instance_id)
        self.assertIsNone(self.dialog_state.current_prompt_state)

    def test_trigger_reminder(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(2)
        command = TriggerReminder(
            phone_number=self.phone_number,
            drill_instance_id=self.dialog_state.drill_instance_id,  # type:ignore
            prompt_slug=self.drill.prompts[2].slug,
        )
        events = self._process_command(command)
        self._assert_event_types(events, DialogEventType.REMINDER_TRIGGERED)

        self.assertTrue(self.dialog_state.current_prompt_state.reminder_triggered)

    def test_trigger_reminder_idempotence(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(2)
        self.dialog_state.current_prompt_state.reminder_triggered = True
        command = TriggerReminder(
            phone_number=self.phone_number,
            drill_instance_id=self.dialog_state.drill_instance_id,  # type:ignore
            prompt_slug=self.drill.prompts[2].slug,
        )
        events = self._process_command(command)
        self.assertEqual(0, len(events))

        self.assertTrue(self.dialog_state.current_prompt_state.reminder_triggered)

    def test_trigger_late_reminder_later_prompt(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(3)
        command = TriggerReminder(
            phone_number=self.phone_number,
            drill_instance_id=self.dialog_state.drill_instance_id,  # type:ignore
            prompt_slug=self.drill.prompts[2].slug,
        )
        events = self._process_command(command)
        self.assertEqual(0, len(events))

        self.assertFalse(self.dialog_state.current_prompt_state.reminder_triggered)

    def test_trigger_late_reminder_later_drill(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(2)
        command = TriggerReminder(self.phone_number, uuid.uuid4(), self.drill.prompts[2].slug)
        events = self._process_command(command)
        self.assertEqual(0, len(events))

        self.assertFalse(self.dialog_state.current_prompt_state.reminder_triggered)


class TestSerialization(unittest.TestCase):
    def setUp(self) -> None:
        self.prompt = Prompt(slug="my-prompt", messages=["one", "two"])
        self.drill = Drill(name="01 START", prompts=[self.prompt])

    def _make_base_assertions(self, original: DialogEvent, deserialized: DialogEvent):
        self.assertEqual(original.event_id, deserialized.event_id)
        self.assertEqual(original.event_type, deserialized.event_type)
        self.assertEqual(original.phone_number, deserialized.phone_number)
        self.assertEqual(original.created_time, deserialized.created_time)

    def test_advanced_to_next_prompt(self):
        original = AdvancedToNextPrompt(
            phone_number="123456789",
            user_profile=UserProfile(True),
            prompt=self.prompt,
            drill_instance_id=uuid.uuid4(),
        )
        serialized = original.to_dict()
        deserialized: AdvancedToNextPrompt = event_from_dict(serialized)  # type: ignore
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.prompt.slug, deserialized.prompt.slug)
        self.assertEqual(original.drill_instance_id, deserialized.drill_instance_id)

    def test_completed_prompt(self):
        original = CompletedPrompt(
            phone_number="123456789",
            user_profile=UserProfile(True),
            prompt=self.prompt,
            response="hello",
            drill_instance_id=uuid.uuid4(),
        )
        serialized = original.to_dict()
        deserialized: CompletedPrompt = event_from_dict(serialized)  # type: ignore
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.prompt.slug, deserialized.prompt.slug)
        self.assertEqual(original.response, deserialized.response)
        self.assertEqual(original.drill_instance_id, deserialized.drill_instance_id)

    def test_failed_prompt(self):
        original = FailedPrompt(
            phone_number="123456789",
            user_profile=UserProfile(True),
            prompt=self.prompt,
            response="hello",
            abandoned=True,
            drill_instance_id=uuid.uuid4(),
        )
        serialized = original.to_dict()
        deserialized: FailedPrompt = event_from_dict(serialized)  # type: ignore
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.prompt.slug, deserialized.prompt.slug)
        self.assertEqual(original.response, deserialized.response)
        self.assertEqual(original.abandoned, deserialized.abandoned)
        self.assertEqual(original.drill_instance_id, deserialized.drill_instance_id)

    def test_drill_started(self):
        original = DrillStarted(
            phone_number="12345678",
            user_profile=UserProfile(True),
            drill=self.drill,
            first_prompt=self.prompt,
            drill_instance_id=uuid.uuid4(),
        )
        serialized = original.to_dict()
        deserialized: DrillStarted = event_from_dict(serialized)  # type: ignore
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.drill.name, deserialized.drill.name)
        self.assertEqual(original.drill_instance_id, deserialized.drill_instance_id)
        self.assertEqual(original.first_prompt.slug, deserialized.first_prompt.slug)

    def test_drill_completed(self):
        original = DrillCompleted(
            phone_number="12345678", user_profile=UserProfile(True), drill_instance_id=uuid.uuid4()
        )
        serialized = original.to_dict()
        deserialized: DrillCompleted = event_from_dict(serialized)  # type: ignore
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.drill_instance_id, deserialized.drill_instance_id)

    def test_reminder_triggered(self):
        original = ReminderTriggered("123456789", user_profile=UserProfile(True))
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)

    def test_user_validated(self):
        original = UserValidated(
            "123456789",
            user_profile=UserProfile(True),
            code_validation_payload=CodeValidationPayload(valid=True, is_demo=True),
        )
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)

    def test_user_validation_failed(self):
        original = UserValidationFailed("123456789", user_profile=UserProfile(True))
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)
