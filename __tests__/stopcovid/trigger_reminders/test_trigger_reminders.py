import unittest
import json
from unittest.mock import patch, MagicMock
import datetime

from stopcovid import db
from stopcovid.trigger_reminders.persistence import ReminderTriggerRepository
from stopcovid.trigger_reminders.trigger_reminders import ReminderTriggerer
from stopcovid.status.drill_instances import DrillInstanceRepository
from __tests__.utils.factories import make_drill_instance


class TestReminderTriggers(unittest.TestCase):
    def setUp(self):
        self.drill_instance_repo = DrillInstanceRepository(db.get_test_sqlalchemy_engine)
        self.drill_instance_repo.drop_and_recreate_tables_testing_only()
        self.reminder_trigger_repo = ReminderTriggerRepository(db.get_test_sqlalchemy_engine)
        self.reminder_trigger_repo.drop_and_recreate_tables_testing_only()
        reminder_db_patch = patch(
            "stopcovid.trigger_reminders.trigger_reminders.ReminderTriggerer._get_reminder_trigger_repo",
            return_value=self.reminder_trigger_repo,
        )
        reminder_db_patch.start()

        drill_db_patch = patch(
            "stopcovid.trigger_reminders.trigger_reminders.ReminderTriggerer._get_drill_instance_repo",
            return_value=self.drill_instance_repo,
        )
        drill_db_patch.start()

        self.kinesis_client = MagicMock()
        kinesis_patch = patch(
            "stopcovid.trigger_reminders.trigger_reminders.ReminderTriggerer._get_kinesis_client",
            return_value=self.kinesis_client,
        )
        kinesis_patch.start()

        self.addCleanup(reminder_db_patch.stop)
        self.addCleanup(drill_db_patch.stop)
        self.addCleanup(kinesis_patch.stop)

    def _get_incomplete_drill_with_last_prompt_started_min_ago(self, min_ago):
        return make_drill_instance(
            current_prompt_start_time=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=min_ago),
            completion_time=None,
        )

    def assert_kinesis_publish(self, drill_instance):
        self.kinesis_client.put_records.assert_called_once()
        _, __, kwargs = self.kinesis_client.put_records.mock_calls[0]
        expected_kinesis_payload = [
            {
                "Data": json.dumps(
                    {
                        "type": "TRIGGER_REMINDER",
                        "payload": {
                            "phone_number": drill_instance.phone_number,
                            "drill_instance_id": str(drill_instance.drill_instance_id),
                            "prompt_slug": drill_instance.current_prompt_slug,
                        },
                    },
                ),
                "PartitionKey": drill_instance.phone_number,
            }
        ]
        self.assertEqual(kwargs["Records"], expected_kinesis_payload)

    def test_reminder_triggerer_ignores_drills_below_inactivity_threshold(self):
        drill_instance = self._get_incomplete_drill_with_last_prompt_started_min_ago(10)
        self.drill_instance_repo._save_drill_instance(drill_instance)
        ReminderTriggerer().trigger_reminders()
        self.kinesis_client.put_records.assert_not_called()
        self.assertEqual(len(self.reminder_trigger_repo.get_reminder_triggers()), 0)

    def test_reminder_triggerer_triggers_reminder(self):
        drill_instance = self._get_incomplete_drill_with_last_prompt_started_min_ago(5 * 60)
        self.drill_instance_repo._save_drill_instance(drill_instance)
        ReminderTriggerer().trigger_reminders()
        persisted_reminder_triggers = self.reminder_trigger_repo.get_reminder_triggers()
        self.assertEqual(len(persisted_reminder_triggers), 1)
        self.assertEqual(
            persisted_reminder_triggers[0].drill_instance_id, drill_instance.drill_instance_id
        )
        self.assertEqual(
            persisted_reminder_triggers[0].prompt_slug, drill_instance.current_prompt_slug
        )
        self.assert_kinesis_publish(drill_instance)

    def test_does_not_double_trigger_reminders(self):
        drill_instance = self._get_incomplete_drill_with_last_prompt_started_min_ago(5 * 60)
        self.drill_instance_repo._save_drill_instance(drill_instance)
        ReminderTriggerer().trigger_reminders()
        persisted_reminder_triggers = self.reminder_trigger_repo.get_reminder_triggers()
        self.assertEqual(len(persisted_reminder_triggers), 1)
        self.assert_kinesis_publish(drill_instance)
        self.kinesis_client.reset_mock()
        ReminderTriggerer().trigger_reminders()
        persisted_reminder_triggers = self.reminder_trigger_repo.get_reminder_triggers()
        self.assertEqual(len(persisted_reminder_triggers), 1)
        self.kinesis_client.put_records.assert_not_called()
