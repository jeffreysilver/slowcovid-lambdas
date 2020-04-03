import unittest
import uuid
import datetime

from stopcovid.dialog.dialog import (
    UserValidated,
    DrillStarted,
    DrillCompleted,
    CompletedPrompt,
    FailedPrompt,
    AdvancedToNextPrompt,
)
from stopcovid.dialog.registration import CodeValidationPayload
from stopcovid.dialog.types import UserProfile, DialogEventBatch
from stopcovid.drills.drills import Drill, Prompt
from stopcovid.status import db
from stopcovid.status.drill_instances import DrillInstanceRepository, DrillInstance


class TestDrillInstances(unittest.TestCase):
    def setUp(self):
        self.repo = DrillInstanceRepository(db.get_test_sqlalchemy_engine)
        self.repo.drop_and_recreate_tables_testing_only()
        self.phone_number = "123456789"
        self.prompt1 = Prompt(slug="first", messages=[])
        self.prompt2 = Prompt(slug="second", messages=[])
        self.drill = Drill(slug="slug", name="name", prompts=[self.prompt1])
        self.seq = 0
        self.drill_instance = self._make_drill_instance()

    def _seq(self) -> str:
        result = str(self.seq)
        self.seq += 1
        return result

    def _make_drill_instance(self, user_id=None) -> DrillInstance:
        if user_id is None:
            user_id = uuid.uuid4()
        return DrillInstance(
            drill_instance_id=uuid.uuid4(),
            seq=self._seq(),
            user_id=user_id,
            phone_number=self.phone_number,
            drill_slug="test",
            current_prompt_slug="test-prompt",
            current_prompt_start_time=datetime.datetime.now(datetime.timezone.utc),
            current_prompt_last_response_time=datetime.datetime.now(datetime.timezone.utc),
            completion_time=None,
            is_valid=True,
        )

    def _make_batch(self, events):
        return DialogEventBatch(phone_number=self.phone_number, events=events, seq=self._seq())

    def test_get_and_save(self):
        self.assertIsNone(self.repo.get_drill_instance(self.drill_instance.drill_instance_id))
        self.repo._save_drill_instance(self.drill_instance)
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(self.drill_instance, retrieved)

    def test_user_revalidated(self):
        drill_instance1 = self._make_drill_instance()
        drill_instance2 = self._make_drill_instance(drill_instance1.user_id)
        self.repo._save_drill_instance(drill_instance1)
        self.repo._save_drill_instance(drill_instance2)
        self.assertTrue(drill_instance1.is_valid)
        self.assertTrue(drill_instance2.is_valid)

        self.repo.update_drill_instances(
            drill_instance1.user_id,
            self._make_batch(
                [
                    UserValidated(
                        phone_number=self.phone_number,
                        user_profile=UserProfile(True),
                        code_validation_payload=CodeValidationPayload(valid=True, is_demo=True),
                    )
                ]
            ),
        )
        drill_instance1 = self.repo.get_drill_instance(drill_instance1.drill_instance_id)
        drill_instance2 = self.repo.get_drill_instance(drill_instance2.drill_instance_id)
        self.assertFalse(drill_instance1.is_valid)
        self.assertFalse(drill_instance2.is_valid)

    def test_user_revalidated_idempotence(self):
        drill_instance1 = self._make_drill_instance()
        drill_instance2 = self._make_drill_instance(drill_instance1.user_id)
        self.repo._save_drill_instance(drill_instance1)
        self.repo._save_drill_instance(drill_instance2)
        self.assertTrue(drill_instance1.is_valid)
        self.assertTrue(drill_instance2.is_valid)

        batch = self._make_batch(
            [
                UserValidated(
                    phone_number=self.phone_number,
                    user_profile=UserProfile(True),
                    code_validation_payload=CodeValidationPayload(valid=True, is_demo=True),
                )
            ]
        )
        batch.seq = drill_instance2.seq
        self.repo.update_drill_instances(drill_instance1.user_id, batch)
        drill_instance1 = self.repo.get_drill_instance(drill_instance1.drill_instance_id)
        drill_instance2 = self.repo.get_drill_instance(drill_instance2.drill_instance_id)
        self.assertFalse(drill_instance1.is_valid)
        self.assertTrue(drill_instance2.is_valid)

    def test_drill_started(self):
        event = DrillStarted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill=self.drill,
            first_prompt=self.prompt1,
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, self._make_batch([event]))
        drill_instance = self.repo.get_drill_instance(event.drill_instance_id)
        self.assertIsNotNone(drill_instance)
        self.assertEqual(event.created_time, drill_instance.current_prompt_start_time)
        self.assertEqual(self.prompt1.slug, drill_instance.current_prompt_slug)
        self.assertIsNone(drill_instance.completion_time)
        self.assertTrue(drill_instance.is_valid)

    def test_drill_completed(self):
        self.repo._save_drill_instance(self.drill_instance)
        event = DrillCompleted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill_instance_id=self.drill_instance.drill_instance_id,
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, self._make_batch([event]))
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(event.created_time, retrieved.completion_time)
        self.assertIsNone(retrieved.current_prompt_last_response_time)
        self.assertIsNone(retrieved.current_prompt_start_time)
        self.assertIsNone(retrieved.current_prompt_slug)

    def test_prompt_completed(self):
        self.repo._save_drill_instance(self.drill_instance)
        event = CompletedPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt1,
            drill_instance_id=self.drill_instance.drill_instance_id,
            response="go",
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, self._make_batch([event]))
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(event.created_time, retrieved.current_prompt_last_response_time)

    def test_prompt_failed(self):
        self.repo._save_drill_instance(self.drill_instance)
        event = FailedPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt1,
            drill_instance_id=self.drill_instance.drill_instance_id,
            response="go",
            abandoned=False,
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, self._make_batch([event]))
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(event.created_time, retrieved.current_prompt_last_response_time)

    def test_advanced_to_next_prompt(self):
        self.repo._save_drill_instance(self.drill_instance)
        event = CompletedPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt1,
            drill_instance_id=self.drill_instance.drill_instance_id,
            response="go",
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, self._make_batch([event]))
        event = AdvancedToNextPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt2,
            drill_instance_id=self.drill_instance.drill_instance_id,
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, self._make_batch([event]))
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(self.prompt2.slug, retrieved.current_prompt_slug)
        self.assertIsNone(retrieved.current_prompt_last_response_time)
        self.assertEqual(event.created_time, retrieved.current_prompt_start_time)

    def test_general_idempotence(self):
        self.repo._save_drill_instance(self.drill_instance)
        event = FailedPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt1,
            drill_instance_id=self.drill_instance.drill_instance_id,
            response="go",
            abandoned=False,
        )
        batch = self._make_batch([event])
        batch.seq = self.drill_instance.seq
        self.repo.update_drill_instances(self.drill_instance.user_id, batch)
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertNotEqual(event.created_time, retrieved.current_prompt_last_response_time)