import unittest

from drills.drills import Prompt, Drill
from .dialog import *
from .types import DialogEvent

"""
    DRILL_COMPLETED = "DRILL_COMPLETED"
"""


class TestSerialization(unittest.TestCase):
    def setUp(self) -> None:
        self.prompt = Prompt(
            slug='my-prompt',
            messages=['one', 'two']
        )
        self.drill = Drill(
            drill_id=uuid.uuid4(),
            prompts=[self.prompt]
        )

    def _make_base_assertions(self, original: DialogEvent, deserialized: DialogEvent):
        self.assertEqual(original.event_id, deserialized.event_id)
        self.assertEqual(original.event_type, deserialized.event_type)
        self.assertEqual(original.phone_number, deserialized.phone_number)
        self.assertEqual(original.created_time, deserialized.created_time)

    def test_advanced_to_next_prompt(self):
        original = AdvancedToNextPrompt(
            phone_number="123456789",
            prompt=self.prompt
        )
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.prompt.slug, deserialized.prompt.slug)

    def test_completed_prompt(self):
        original = CompletedPrompt(
            phone_number="123456789",
            prompt=self.prompt,
            response="hello"
        )
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.prompt.slug, deserialized.prompt.slug)
        self.assertEqual(original.response, deserialized.response)

    def test_failed_prompt(self):
        original = FailedPrompt(
            phone_number="123456789",
            prompt=self.prompt,
            response="hello",
            abandoned=True
        )
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.prompt.slug, deserialized.prompt.slug)
        self.assertEqual(original.response, deserialized.response)
        self.assertEqual(original.abandoned, deserialized.abandoned)

    def test_drill_started(self):
        original = DrillStarted(
            phone_number="12345678",
            drill=self.drill
        )
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.drill.drill_id, deserialized.drill.drill_id)

    def test_drill_completed(self):
        original = DrillCompleted(
            phone_number="12345678",
            drill=self.drill
        )
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)
        self.assertEqual(original.drill.drill_id, deserialized.drill.drill_id)

    def test_reminder_triggered(self):
        original = ReminderTriggered("123456789")
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)

    def test_user_created(self):
        original = UserCreated("123456789")
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)

    def test_user_creation_failed(self):
        original = UserCreationFailed("123456789")
        serialized = original.to_dict()
        deserialized = event_from_dict(serialized)
        self._make_base_assertions(original, deserialized)
