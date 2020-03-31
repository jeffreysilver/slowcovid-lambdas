import unittest

from stopcovid.drills.drills import Prompt, Drill
from stopcovid.dialog.dialog import *
from stopcovid.dialog.types import DialogEvent, UserProfile


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
        deserialized = event_from_dict(serialized)
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
        deserialized = event_from_dict(serialized)
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
        deserialized = event_from_dict(serialized)
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
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.drill.name, deserialized.drill.name)
        self.assertEqual(original.drill_instance_id, deserialized.drill_instance_id)
        self.assertEqual(original.first_prompt.slug, deserialized.first_prompt.slug)

    def test_drill_completed(self):
        original = DrillCompleted(
            phone_number="12345678", user_profile=UserProfile(True), drill_instance_id=uuid.uuid4()
        )
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
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
