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
    slug="test-drill",
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

NOW = datetime.datetime.now(datetime.timezone.utc)


class TestProcessCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.phone_number = "123456789"
        self.dialog_state = DialogState(phone_number=self.phone_number, seq="0")
        self.drill = DRILL
        self.repo = MagicMock()
        self.repo.fetch_dialog_state = MagicMock(return_value=self.dialog_state)
        self.repo.persist_dialog_state = MagicMock()
        self.next_seq = 1
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
        self.assertEqual(len(args), len(events), f"{args} vs {events}")
        for i in range(len(events)):
            self.assertEqual(args[i], events[i].event_type)

    def _set_current_prompt(self, prompt_index: int, should_advance: bool):
        self.dialog_state.current_drill = self.drill
        underlying_prompt = self.drill.prompts[prompt_index]
        prompt = Mock(wraps=underlying_prompt)
        prompt.slug = underlying_prompt.slug
        prompt.messages = underlying_prompt.messages
        prompt.response_user_profile_key = underlying_prompt.response_user_profile_key
        prompt.max_failures = underlying_prompt.max_failures
        prompt.should_advance_with_answer.return_value = should_advance
        self.drill.prompts[prompt_index] = prompt
        self.dialog_state.current_prompt_state = PromptState(slug=prompt.slug, start_time=self.now)

    def test_skip_processed_sequence_numbers(self):
        command = Mock(wraps=ProcessSMSMessage(self.phone_number, "hey"))
        process_command(command, "0", repo=self.repo)
        self.assertFalse(command.execute.called)

    def test_advance_sequence_numbers(self):
        validator = MagicMock()
        validation_payload = CodeValidationPayload(valid=True, account_info={"company": "WeWork"})
        validator.validate_code = MagicMock(return_value=validation_payload)
        command = ProcessSMSMessage(self.phone_number, "hey", registration_validator=validator)
        events = self._process_command(command)
        self.assertEqual(1, len(events))
        self.assertEqual("1", self.dialog_state.seq)

    def test_first_message_validates_user(self):
        validator = MagicMock()
        validation_payload = CodeValidationPayload(valid=True, account_info={"company": "WeWork"})
        validator.validate_code = MagicMock(return_value=validation_payload)
        command = ProcessSMSMessage(self.phone_number, "hey", registration_validator=validator)
        self.assertFalse(self.dialog_state.user_profile.validated)

        events = self._process_command(command)
        self._assert_event_types(events, DialogEventType.USER_VALIDATED)
        self.assertEqual(validation_payload, events[0].code_validation_payload)

    def test_first_message_does_not_validate_user(self):
        validator = MagicMock()
        validation_payload = CodeValidationPayload(valid=False)
        validator.validate_code = MagicMock(return_value=validation_payload)
        command = ProcessSMSMessage(self.phone_number, "hey", registration_validator=validator)
        self.assertFalse(self.dialog_state.user_profile.validated)

        events = self._process_command(command)

        self._assert_event_types(events, DialogEventType.USER_VALIDATION_FAILED)

    def test_start_drill(self):
        self.dialog_state.user_profile.validated = True
        command = StartDrill(self.phone_number, self.drill)

        events = self._process_command(command)

        self._assert_event_types(events, DialogEventType.DRILL_STARTED)
        self.assertEqual(self.drill, events[0].drill)
        self.assertEqual(self.drill.first_prompt(), events[0].first_prompt)
        self.assertIsNotNone(events[0].drill_instance_id)

    def test_complete_and_advance(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(0, should_advance=True)
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

    def test_repeat_with_wrong_answer(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(2, should_advance=False)
        command = ProcessSMSMessage(self.phone_number, "completely wrong answer")
        events = self._process_command(command)
        self._assert_event_types(events, DialogEventType.FAILED_PROMPT)

        failed_event: FailedPrompt = events[0]
        self.assertEqual(failed_event.prompt, self.drill.prompts[2])
        self.assertFalse(failed_event.abandoned)
        self.assertEqual(failed_event.response, "completely wrong answer")
        self.assertEqual(failed_event.drill_instance_id, self.dialog_state.drill_instance_id)

    def test_advance_with_too_many_wrong_answers(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(2, should_advance=False)
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

    def test_conclude_with_right_answer(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(3, should_advance=True)
        command = ProcessSMSMessage(self.phone_number, "foo")
        events = self._process_command(command)
        self._assert_event_types(
            events,
            DialogEventType.COMPLETED_PROMPT,
            DialogEventType.ADVANCED_TO_NEXT_PROMPT,
            DialogEventType.DRILL_COMPLETED,
        )
        completed_event: CompletedPrompt = events[0]
        self.assertEqual(completed_event.prompt, self.drill.prompts[3])
        self.assertEqual(completed_event.response, "foo")
        self.assertEqual(completed_event.drill_instance_id, self.dialog_state.drill_instance_id)

        advanced_event: AdvancedToNextPrompt = events[1]
        self.assertEqual(self.drill.prompts[4], advanced_event.prompt)

        self.assertEqual(self.dialog_state.drill_instance_id, advanced_event.drill_instance_id)

        drill_completed_event: DrillCompleted = events[2]
        self.assertEqual(
            self.dialog_state.drill_instance_id, drill_completed_event.drill_instance_id
        )

    def test_conclude_with_too_many_wrong_answers(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(3, should_advance=False)
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

    def test_trigger_reminder(self):
        self.dialog_state.user_profile.validated = True
        self._set_current_prompt(2, should_advance=True)
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
        self._set_current_prompt(2, should_advance=True)
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
        self._set_current_prompt(3, should_advance=True)
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
        self._set_current_prompt(2, should_advance=True)
        command = TriggerReminder(self.phone_number, uuid.uuid4(), self.drill.prompts[2].slug)
        events = self._process_command(command)
        self.assertEqual(0, len(events))

        self.assertFalse(self.dialog_state.current_prompt_state.reminder_triggered)


class TestUserValidationEvents(unittest.TestCase):
    def test_user_validated(self):
        profile = UserProfile(validated=False)
        dialog_state = DialogState("123456789", "0", user_profile=profile)
        event = UserValidated(
            phone_number="123456789",
            user_profile=profile,
            code_validation_payload=CodeValidationPayload(
                valid=True, is_demo=False, account_info={"foo": "bar"}
            ),
        )
        event.apply_to(dialog_state)
        self.assertTrue(dialog_state.user_profile.validated)
        self.assertEqual({"foo": "bar"}, dialog_state.user_profile.account_info)

    def test_user_validation_failed(self):
        profile = UserProfile(validated=False)
        dialog_state = DialogState("123456789", "0", user_profile=profile)
        event = UserValidationFailed(phone_number="123456789", user_profile=profile)
        event.apply_to(dialog_state)
        self.assertFalse(dialog_state.user_profile.validated)


class TestStartDrill(unittest.TestCase):
    def test_start_drill(self):
        profile = UserProfile(validated=True)
        event = DrillStarted(
            phone_number="123456789",
            user_profile=profile,
            drill=DRILL,
            first_prompt=DRILL.prompts[0],
        )
        dialog_state = DialogState(phone_number="123456789", seq="0", user_profile=profile)
        event.apply_to(dialog_state)
        self.assertEqual(DRILL, dialog_state.current_drill)
        self.assertEqual(
            PromptState(slug=DRILL.prompts[0].slug, start_time=event.created_time),
            dialog_state.current_prompt_state,
        )
        self.assertEqual(event.drill_instance_id, dialog_state.drill_instance_id)


class TestCompletedPrompt(unittest.TestCase):
    def test_completed_and_not_stored(self):
        profile = UserProfile(validated=True)
        event = CompletedPrompt(
            "123456789",
            user_profile=profile,
            prompt=DRILL.prompts[0],
            drill_instance_id=uuid.uuid4(),
            response="go",
        )
        dialog_state = DialogState(
            "123456789",
            "0",
            user_profile=profile,
            current_drill=DRILL,
            current_prompt_state=PromptState(DRILL.prompts[0].slug, NOW),
        )
        event.apply_to(dialog_state)
        self.assertEqual(profile, dialog_state.user_profile)
        self.assertIsNone(dialog_state.current_prompt_state)

    def test_completed_and_stored(self):
        profile = UserProfile(validated=True)
        event = CompletedPrompt(
            "123456789",
            user_profile=profile,
            prompt=DRILL.prompts[1],
            drill_instance_id=uuid.uuid4(),
            response="7",
        )
        dialog_state = DialogState(
            "123456789",
            "0",
            user_profile=profile,
            current_drill=DRILL,
            current_prompt_state=PromptState(DRILL.prompts[0].slug, NOW),
        )
        event.apply_to(dialog_state)
        self.assertEqual(UserProfile(validated=True, self_rating_1="7"), dialog_state.user_profile)
        self.assertIsNone(dialog_state.current_prompt_state)


class TestFailedPrompt(unittest.TestCase):
    def test_failed_and_not_abandoned(self):
        profile = UserProfile(validated=True)
        event = FailedPrompt(
            phone_number="123456789",
            user_profile=profile,
            prompt=DRILL.prompts[2],
            drill_instance_id=uuid.uuid4(),
            response="b",
            abandoned=False,
        )
        dialog_state = DialogState(
            "123456789",
            seq="0",
            user_profile=profile,
            current_drill=DRILL,
            drill_instance_id=event.drill_instance_id,
            current_prompt_state=PromptState(DRILL.prompts[2].slug, start_time=NOW),
        )
        event.apply_to(dialog_state)
        self.assertEqual(
            PromptState(
                slug=DRILL.prompts[2].slug,
                start_time=NOW,
                last_response_time=event.created_time,
                failures=1,
            ),
            dialog_state.current_prompt_state,
        )

    def test_failed_and_abandoned(self):
        profile = UserProfile(validated=True)
        event = FailedPrompt(
            phone_number="123456789",
            user_profile=profile,
            prompt=DRILL.prompts[2],
            drill_instance_id=uuid.uuid4(),
            response="b",
            abandoned=True,
        )
        dialog_state = DialogState(
            "123456789",
            seq="0",
            user_profile=profile,
            current_drill=DRILL,
            drill_instance_id=event.drill_instance_id,
            current_prompt_state=PromptState(DRILL.prompts[2].slug, start_time=NOW),
        )
        event.apply_to(dialog_state)
        self.assertIsNone(dialog_state.current_prompt_state)


class TestAdvancedToNextPrompt(unittest.TestCase):
    def test_advanced_to_next_prompt(self):
        profile = UserProfile(validated=True)
        event = AdvancedToNextPrompt(
            phone_number="123456789",
            user_profile=profile,
            prompt=DRILL.prompts[1],
            drill_instance_id=uuid.uuid4(),
        )
        dialog_state = DialogState(
            "123456789",
            seq="0",
            user_profile=profile,
            current_drill=DRILL,
            drill_instance_id=event.drill_instance_id,
            current_prompt_state=PromptState(DRILL.prompts[0].slug, start_time=NOW),
        )
        event.apply_to(dialog_state)
        self.assertEqual(
            PromptState(DRILL.prompts[1].slug, start_time=event.created_time),
            dialog_state.current_prompt_state,
        )


class TestDrillCompleted(unittest.TestCase):
    def test_drill_completed(self):
        profile = UserProfile(validated=False)
        event = DrillCompleted("123456789", user_profile=profile, drill_instance_id=uuid.uuid4())
        dialog_state = DialogState(
            "123456789",
            seq="0",
            user_profile=profile,
            current_drill=DRILL,
            drill_instance_id=event.drill_instance_id,
            current_prompt_state=PromptState(DRILL.prompts[-1].slug, start_time=NOW),
        )
        event.apply_to(dialog_state)
        self.assertIsNone(dialog_state.drill_instance_id)
        self.assertIsNone(dialog_state.current_prompt_state)
        self.assertIsNone(dialog_state.current_drill)


class TestSerialization(unittest.TestCase):
    def setUp(self) -> None:
        self.prompt = Prompt(slug="my-prompt", messages=["one", "two"])
        self.drill = Drill(name="01 START", slug="01-start", prompts=[self.prompt])

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
