import unittest
import uuid
from copy import copy

from stopcovid.dialog.dialog import (
    UserValidated,
    DrillStarted,
    DrillCompleted,
    CompletedPrompt,
    FailedPrompt,
)
from stopcovid.dialog.registration import CodeValidationPayload
from stopcovid.dialog.types import UserProfile, DialogEventBatch
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
        self.seq = 0

    def _seq(self):
        result = str(self.seq)
        self.seq += 1
        return result

    def test_create_or_update_user(self):
        batch = DialogEventBatch(
            phone_number=self.phone_number,
            seq=self._seq(),
            events=[
                DrillCompleted(
                    phone_number=self.phone_number,
                    user_profile=UserProfile(True, account_info={"foo": "bar"}),
                    drill_instance_id=uuid.uuid4(),
                )
            ],
        )
        user_id = self.repo._create_or_update_user(batch, self.repo.engine)
        user = self.repo.get_user(user_id)
        self.assertEqual(user_id, user.user_id)
        self.assertEqual({"foo": "bar"}, user.account_info)
        self.assertIsNone(user.last_interacted_time)
        self.assertEqual(batch.seq, user.seq)

        batch2 = self._make_batch(
            [
                DrillCompleted(
                    phone_number=self.phone_number,
                    user_profile=UserProfile(True, account_info={"foo": "bar", "one": "two"}),
                    drill_instance_id=uuid.uuid4(),
                )
            ]
        )

        self.repo._create_or_update_user(batch2, self.repo.engine)
        user = self.repo.get_user(user_id)
        self.assertEqual({"foo": "bar", "one": "two"}, user.account_info)
        self.assertEqual(batch2.seq, user.seq)

    def _make_user_and_get_id(self) -> uuid.UUID:
        return self.repo._create_or_update_user(
            self._make_batch(
                [
                    UserValidated(
                        phone_number=self.phone_number,
                        user_profile=UserProfile(True),
                        code_validation_payload=CodeValidationPayload(valid=True),
                    )
                ]
            ),
            self.repo.engine,
        )

    def _make_batch(self, events) -> DialogEventBatch:
        return DialogEventBatch(
            phone_number=self.phone_number, seq=self._seq(), events=events, batch_id=uuid.uuid4()
        )

    def test_user_revalidated(self):
        user_id = self._make_user_and_get_id()
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
            self.repo._mark_drill_started(user_id, event, self.repo.engine)
            self.repo._mark_drill_completed(user_id, event2, self.repo.engine)
            drill_status = self.repo.get_drill_status(user_id, slug)
            self.assertIsNotNone(drill_status.started_time)
            self.assertIsNotNone(drill_status.completed_time)
        self.repo.update_user(
            self._make_batch(
                [
                    UserValidated(
                        phone_number=self.phone_number,
                        user_profile=UserProfile(True),
                        code_validation_payload=CodeValidationPayload(valid=True),
                    )
                ]
            )
        )
        for slug in ALL_DRILL_SLUGS:
            drill_status = self.repo.get_drill_status(user_id, slug)
            self.assertIsNone(drill_status.started_time)
            self.assertIsNone(drill_status.completed_time)

    def test_drill_started_and_completed(self):
        user_id = self._make_user_and_get_id()
        event = DrillStarted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill=self.drill,
            first_prompt=self.prompt,
        )
        self.repo.update_user(self._make_batch([event]))
        drill_status = self.repo.get_drill_status(user_id, self.prompt.slug)
        self.assertEqual(event.created_time, drill_status.started_time)
        self.assertIsNone(drill_status.completed_time)

        event2 = DrillCompleted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill_instance_id=event.drill_instance_id,
        )
        self.repo.update_user(self._make_batch([event2]))
        drill_status = self.repo.get_drill_status(user_id, self.prompt.slug)
        self.assertEqual(event.created_time, drill_status.started_time)
        self.assertEqual(event2.created_time, drill_status.completed_time)

    def test_completed_prompt(self):
        user_id = self._make_user_and_get_id()
        event = DrillStarted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill=self.drill,
            first_prompt=self.prompt,
        )
        self.repo.update_user(self._make_batch([event]))
        user = self.repo.get_user(user_id)
        self.assertIsNone(user.last_interacted_time)
        event2 = CompletedPrompt(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            prompt=self.prompt,
            drill_instance_id=event.drill_instance_id,
            response="go",
        )
        self.repo.update_user(self._make_batch([event2]))
        user = self.repo.get_user(user_id)
        self.assertEqual(event2.created_time, user.last_interacted_time)

    def test_failed_prompt(self):
        user_id = self._make_user_and_get_id()
        event = DrillStarted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill=self.drill,
            first_prompt=self.prompt,
        )
        self.repo.update_user(self._make_batch([event]))
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
        self.repo.update_user(self._make_batch([event2]))
        user = self.repo.get_user(user_id)
        self.assertEqual(event2.created_time, user.last_interacted_time)

    def test_idempotence(self):
        user_id = self._make_user_and_get_id()
        event = DrillStarted(
            phone_number=self.phone_number,
            user_profile=UserProfile(True),
            drill=self.drill,
            first_prompt=self.prompt,
        )
        batch1 = self._make_batch([event])
        self.repo.update_user(batch1)
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
        batch2 = self._make_batch([event2])
        batch2.seq = batch1.seq
        self.repo.update_user(batch2)
        user = self.repo.get_user(user_id)
        self.assertIsNone(user.last_interacted_time)
