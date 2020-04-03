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
from stopcovid.dialog.types import UserProfile
from stopcovid.drills.drills import Drill, Prompt
from stopcovid.status import db
from stopcovid.status.drill_instances import DrillInstanceRepository, DrillInstance


class TestDrillInstances(unittest.TestCase):
    def setUp(self):
        self.repo = DrillInstanceRepository(db.get_test_sqlalchemy_engine)
        self.repo.drop_and_recreate_tables_testing_only()
        self.phone_number = "123456789"
        self.drill_instance = self._make_drill_instance()
        self.prompt1 = Prompt(slug="first", messages=[])
        self.prompt2 = Prompt(slug="second", messages=[])
        self.drill = Drill(slug="slug", name="name", prompts=[self.prompt1])

    def _make_drill_instance(self, **overrides) -> DrillInstance:
        def _get_value(key, default):
            return overrides[key] if key in overrides else default

        return DrillInstance(
            drill_instance_id=_get_value("drill_instance_id", uuid.uuid4()),
            user_id=_get_value("user_id", uuid.uuid4()),
            phone_number=_get_value("phone_number", self.phone_number),
            drill_slug=_get_value("drill_slug", "test"),
            current_prompt_slug=_get_value("current_prompt_slug", "test-prompt"),
            current_prompt_start_time=_get_value(
                "current_prompt_start_time", datetime.datetime.now(datetime.timezone.utc)
            ),
            current_prompt_last_response_time=_get_value(
                "current_prompt_last_response_time", datetime.datetime.now(datetime.timezone.utc)
            ),
            completion_time=_get_value("completion_time", None),
            is_valid=_get_value("is_valid", True),
        )

    def test_get_and_save(self):
        self.assertIsNone(self.repo.get_drill_instance(self.drill_instance.drill_instance_id))
        self.repo.save_drill_instance(self.drill_instance)
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(self.drill_instance, retrieved)
        self.drill_instance.completion_time = datetime.datetime.now(datetime.timezone.utc)
        self.repo.save_drill_instance(self.drill_instance)
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(self.drill_instance, retrieved)

    def test_user_revalidated(self):
        drill_instance1 = self._make_drill_instance()
        drill_instance2 = self._make_drill_instance(user_id=drill_instance1.user_id)
        self.repo.save_drill_instance(drill_instance1)
        self.repo.save_drill_instance(drill_instance2)
        self.assertTrue(drill_instance1.is_valid)
        self.assertTrue(drill_instance2.is_valid)

        self.repo.update_drill_instances(
            drill_instance1.user_id,
            UserValidated(
                phone_number=self.phone_number,
                user_profile=UserProfile(True),
                code_validation_payload=CodeValidationPayload(valid=True, is_demo=True),
            ),
        )
        drill_instance1 = self.repo.get_drill_instance(drill_instance1.drill_instance_id)
        drill_instance2 = self.repo.get_drill_instance(drill_instance2.drill_instance_id)
        self.assertFalse(drill_instance1.is_valid)
        self.assertFalse(drill_instance2.is_valid)

    def test_drill_started(self):
        event = DrillStarted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill=self.drill,
            first_prompt=self.prompt1,
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, event)
        drill_instance = self.repo.get_drill_instance(event.drill_instance_id)
        self.assertIsNotNone(drill_instance)
        self.assertEqual(event.created_time, drill_instance.current_prompt_start_time)
        self.assertEqual(self.prompt1.slug, drill_instance.current_prompt_slug)
        self.assertIsNone(drill_instance.completion_time)
        self.assertTrue(drill_instance.is_valid)

    def test_drill_completed(self):
        self.repo.save_drill_instance(self.drill_instance)
        event = DrillCompleted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill_instance_id=self.drill_instance.drill_instance_id,
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, event)
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(event.created_time, retrieved.completion_time)
        self.assertIsNone(retrieved.current_prompt_last_response_time)
        self.assertIsNone(retrieved.current_prompt_start_time)
        self.assertIsNone(retrieved.current_prompt_slug)

    def test_prompt_completed(self):
        self.repo.save_drill_instance(self.drill_instance)
        event = CompletedPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt1,
            drill_instance_id=self.drill_instance.drill_instance_id,
            response="go",
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, event)
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(event.created_time, retrieved.current_prompt_last_response_time)

    def test_prompt_failed(self):
        self.repo.save_drill_instance(self.drill_instance)
        event = FailedPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt1,
            drill_instance_id=self.drill_instance.drill_instance_id,
            response="go",
            abandoned=False,
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, event)
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(event.created_time, retrieved.current_prompt_last_response_time)

    def test_advanced_to_next_prompt(self):
        self.repo.save_drill_instance(self.drill_instance)
        event = CompletedPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt1,
            drill_instance_id=self.drill_instance.drill_instance_id,
            response="go",
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, event)
        event = AdvancedToNextPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt2,
            drill_instance_id=self.drill_instance.drill_instance_id,
        )
        self.repo.update_drill_instances(self.drill_instance.user_id, event)
        retrieved = self.repo.get_drill_instance(self.drill_instance.drill_instance_id)
        self.assertEqual(self.prompt2.slug, retrieved.current_prompt_slug)
        self.assertIsNone(retrieved.current_prompt_last_response_time)
        self.assertEqual(event.created_time, retrieved.current_prompt_start_time)

    def test_get_incomplete_drills(self):
        incomplete_drill_instance = self._make_drill_instance(completion_time=None)
        complete_drill_instance = self._make_drill_instance(
            completion_time=datetime.datetime.now(datetime.timezone.utc)
        )
        self.repo.save_drill_instance(incomplete_drill_instance)
        self.repo.save_drill_instance(complete_drill_instance)
        results = self.repo.get_incomplete_drills()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].drill_instance_id, incomplete_drill_instance.drill_instance_id)

    def test_get_incomplete_drills_with_inactive_for_minutes(self):
        just_started_drill_instance = self._make_drill_instance(
            current_prompt_start_time=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=-2),
            completion_time=None,
        )
        stale_drill_instance_1 = self._make_drill_instance(
            current_prompt_start_time=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=-61),
            completion_time=None,
        )
        stale_drill_instance_2 = self._make_drill_instance(
            current_prompt_start_time=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=-120),
            completion_time=None,
        )
        complete_drill_instance = self._make_drill_instance(
            completion_time=datetime.datetime.now(datetime.timezone.utc)
        )
        self.repo.save_drill_instance(just_started_drill_instance)
        self.repo.save_drill_instance(stale_drill_instance_1)
        self.repo.save_drill_instance(stale_drill_instance_2)
        self.repo.save_drill_instance(complete_drill_instance)
        results = self.repo.get_incomplete_drills(inactive_for_minutes=60)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].drill_instance_id, stale_drill_instance_1.drill_instance_id)
        self.assertEqual(results[1].drill_instance_id, stale_drill_instance_2.drill_instance_id)
