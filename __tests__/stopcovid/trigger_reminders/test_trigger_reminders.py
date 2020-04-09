import unittest
import uuid
from unittest.mock import patch
import datetime

from stopcovid import db
from stopcovid.dialog.models.events import DialogEventBatch, UserValidated
from stopcovid.dialog.models.state import UserProfile
from stopcovid.dialog.registration import CodeValidationPayload
from stopcovid.trigger_reminders.persistence import ReminderTriggerRepository
from stopcovid.trigger_reminders.trigger_reminders import ReminderTriggerer
from stopcovid.status.drill_progress import DrillProgressRepository
from __tests__.utils.factories import make_drill_instance


@patch("stopcovid.dialog.command_stream.publish.CommandPublisher.publish_trigger_reminder_commands")
class TestReminderTriggers(unittest.TestCase):
    def setUp(self):
        self.drill_progress_repo = DrillProgressRepository(db.get_test_sqlalchemy_engine)
        self.drill_progress_repo.drop_and_recreate_tables_testing_only()
        self.phone_number = "123456789"
        self.user_id = self.drill_progress_repo._create_or_update_user(
            DialogEventBatch(
                events=[
                    UserValidated(self.phone_number, UserProfile(True), CodeValidationPayload(True))
                ],
                phone_number=self.phone_number,
                seq="0",
                batch_id=uuid.uuid4(),
            ),
            None,
            self.drill_progress_repo.engine,
        )
        self.reminder_trigger_repo = ReminderTriggerRepository(db.get_test_sqlalchemy_engine)
        self.reminder_trigger_repo.drop_and_recreate_tables_testing_only()
        reminder_db_patch = patch(
            "stopcovid.trigger_reminders.trigger_reminders.ReminderTriggerer._get_reminder_trigger_repo",
            return_value=self.reminder_trigger_repo,
        )
        reminder_db_patch.start()

        drill_db_patch = patch(
            "stopcovid.trigger_reminders.trigger_reminders.ReminderTriggerer._get_drill_progress_repo",
            return_value=self.drill_progress_repo,
        )
        drill_db_patch.start()

        self.addCleanup(reminder_db_patch.stop)
        self.addCleanup(drill_db_patch.stop)

    def _get_incomplete_drill_with_last_prompt_started_min_ago(self, min_ago):
        return make_drill_instance(
            current_prompt_start_time=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=min_ago),
            completion_time=None,
            user_id=self.user_id,
        )

    def test_reminder_triggerer_ignores_drills_below_inactivity_threshold(self, publish_mock):
        drill_instance = self._get_incomplete_drill_with_last_prompt_started_min_ago(10)
        self.drill_progress_repo._save_drill_instance(drill_instance)
        ReminderTriggerer().trigger_reminders()
        publish_mock.assert_not_called()
        self.assertEqual(len(self.reminder_trigger_repo.get_reminder_triggers()), 0)

    def test_reminder_triggerer_ignores_drills_above_inactivity_threshold(self, publish_mock):
        two_day_old_drill_instance = self._get_incomplete_drill_with_last_prompt_started_min_ago(
            60 * 24 * 2
        )
        self.drill_progress_repo._save_drill_instance(two_day_old_drill_instance)
        ReminderTriggerer().trigger_reminders()
        publish_mock.assert_not_called()
        self.assertEqual(len(self.reminder_trigger_repo.get_reminder_triggers()), 0)

    def test_reminder_triggerer_triggers_reminder(self, publish_mock):
        drill_instance = self._get_incomplete_drill_with_last_prompt_started_min_ago(5 * 60)
        self.drill_progress_repo._save_drill_instance(drill_instance)
        ReminderTriggerer().trigger_reminders()
        persisted_reminder_triggers = self.reminder_trigger_repo.get_reminder_triggers()
        self.assertEqual(len(persisted_reminder_triggers), 1)
        self.assertEqual(
            persisted_reminder_triggers[0].drill_instance_id, drill_instance.drill_instance_id
        )
        self.assertEqual(
            persisted_reminder_triggers[0].prompt_slug, drill_instance.current_prompt_slug
        )
        publish_mock.assert_called_once_with([drill_instance])

    def test_does_not_double_trigger_reminders(self, publish_mock):
        drill_instance = self._get_incomplete_drill_with_last_prompt_started_min_ago(5 * 60)
        self.drill_progress_repo._save_drill_instance(drill_instance)
        ReminderTriggerer().trigger_reminders()
        persisted_reminder_triggers = self.reminder_trigger_repo.get_reminder_triggers()
        self.assertEqual(len(persisted_reminder_triggers), 1)
        publish_mock.assert_called_once_with([drill_instance])
        publish_mock.reset_mock()
        ReminderTriggerer().trigger_reminders()
        persisted_reminder_triggers = self.reminder_trigger_repo.get_reminder_triggers()
        self.assertEqual(len(persisted_reminder_triggers), 1)
        publish_mock.assert_not_called()
