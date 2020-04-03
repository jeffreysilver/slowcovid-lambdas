import unittest
import datetime
from copy import copy

from stopcovid.dialog.dialog import (
    UserValidated,
    DrillStarted,
    DrillCompleted,
    CompletedPrompt,
    FailedPrompt,
)
from stopcovid.dialog.registration import CodeValidationPayload
from stopcovid.dialog.types import UserProfile
from stopcovid.drills.drills import Prompt, Drill
from stopcovid.status.db import get_test_sqlalchemy_engine
from stopcovid.status.users import UserRepository, ALL_DRILL_SLUGS


class TestUsers(unittest.TestCase):
    def setUp(self):
        self.repo = UserRepository(get_test_sqlalchemy_engine)
        self.repo.drop_and_recreate_tables_testing_only()
        self.phone_number = "123456789"
        self.prompt = Prompt(slug="first", messages=[])
        self.drill = Drill(slug="slug", name="name", prompts=[self.prompt])

    def test_create_or_update_user(self):
        profile = UserProfile(True, account_info={"foo": "bar"})
        user_id = self.repo.create_or_update_user(self.phone_number, profile)
        user = self.repo.get_user(user_id)
        self.assertEqual(user_id, user.user_id)
        self.assertEqual({"foo": "bar"}, user.account_info)
        self.assertIsNone(user.last_interacted_time)

        profile.account_info["one"] = "two"
        self.repo.create_or_update_user(self.phone_number, profile)
        user = self.repo.get_user(user_id)
        self.assertEqual({"foo": "bar", "one": "two"}, user.account_info)

    def test_user_revalidated(self):
        user_id = self.repo.create_or_update_user(self.phone_number, UserProfile(True))
        time = datetime.datetime.now(datetime.timezone.utc)
        for slug in ALL_DRILL_SLUGS:
            drill = copy(self.drill)
            drill.slug = slug
            event = DrillStarted(
                phone_number=self.phone_number,
                user_profile=UserProfile(True),
                drill=self.drill,
                first_prompt=self.prompt,
            )
            event2 = DrillCompleted(
                phone_number=self.phone_number,
                user_profile=UserProfile(True),
                drill_instance_id=event.drill_instance_id,
            )
            self.repo._mark_drill_started(user_id, event)
            self.repo._mark_drill_completed(user_id, event2)
            drill_status = self.repo.get_drill_status(user_id, slug)
            self.assertIsNotNone(drill_status.started_time)
            self.assertIsNotNone(drill_status.completed_time)
        self.repo.update_user_progress(
            user_id,
            UserValidated(
                phone_number=self.phone_number,
                user_profile=UserProfile(True),
                code_validation_payload=CodeValidationPayload(valid=True),
            ),
        )
        for slug in ALL_DRILL_SLUGS:
            drill_status = self.repo.get_drill_status(user_id, slug)
            self.assertIsNone(drill_status.started_time)
            self.assertIsNone(drill_status.completed_time)

    def test_drill_started_and_completed(self):
        user_id = self.repo.create_or_update_user(self.phone_number, UserProfile(True))
        event = DrillStarted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill=self.drill,
            first_prompt=self.prompt,
        )
        self.repo.update_user_progress(user_id, event)
        drill_status = self.repo.get_drill_status(user_id, self.prompt.slug)
        self.assertEqual(event.created_time, drill_status.started_time)
        self.assertIsNone(drill_status.completed_time)

        event2 = DrillCompleted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill_instance_id=event.drill_instance_id,
        )
        self.repo.update_user_progress(user_id, event2)
        drill_status = self.repo.get_drill_status(user_id, self.prompt.slug)
        self.assertEqual(event.created_time, drill_status.started_time)
        self.assertEqual(event2.created_time, drill_status.completed_time)

    def test_completed_prompt(self):
        user_id = self.repo.create_or_update_user(self.phone_number, UserProfile(True))
        event = DrillStarted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill=self.drill,
            first_prompt=self.prompt,
        )
        self.repo.update_user_progress(user_id, event)
        user = self.repo.get_user(user_id)
        self.assertIsNone(user.last_interacted_time)
        event2 = CompletedPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt,
            drill_instance_id=event.drill_instance_id,
            response="go",
        )
        self.repo.update_user_progress(user_id, event2)
        user = self.repo.get_user(user_id)
        self.assertEqual(event2.created_time, user.last_interacted_time)

    def test_failed_prompt(self):
        user_id = self.repo.create_or_update_user(self.phone_number, UserProfile(True))
        event = DrillStarted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill=self.drill,
            first_prompt=self.prompt,
        )
        self.repo.update_user_progress(user_id, event)
        user = self.repo.get_user(user_id)
        self.assertIsNone(user.last_interacted_time)
        event2 = FailedPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt,
            drill_instance_id=event.drill_instance_id,
            response="go",
            abandoned=True,
        )
        self.repo.update_user_progress(user_id, event2)
        user = self.repo.get_user(user_id)
        self.assertEqual(event2.created_time, user.last_interacted_time)
