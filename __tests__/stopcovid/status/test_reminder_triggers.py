import unittest
import uuid


from stopcovid.status import db
from stopcovid.status.reminder_triggers import ReminderTriggerRepository, ReminderTrigger


class TestReminderTriggers(unittest.TestCase):
    def setUp(self):
        self.repo = ReminderTriggerRepository(db.get_test_sqlalchemy_engine)
        self.repo.drop_and_recreate_tables_testing_only()

    def test_bulk_create_and_select(self):
        reminder_triggers = [
            ReminderTrigger(id=uuid.uuid4(), drill_instance_id=uuid.uuid4(), prompt_slug="slug-1"),
            ReminderTrigger(id=uuid.uuid4(), drill_instance_id=uuid.uuid4(), prompt_slug="slug-2"),
            ReminderTrigger(id=uuid.uuid4(), drill_instance_id=uuid.uuid4(), prompt_slug="slug-3"),
        ]
        self.repo.save_reminder_triggers(reminder_triggers)
        results = self.repo.get_reminder_triggers()
        self.assertEqual(len(results), 3)
        for obj, persisted_obj in zip(reminder_triggers, results):
            self.assertEqual(obj.id, persisted_obj.id)
            self.assertEqual(obj.drill_instance_id, persisted_obj.drill_instance_id)
            self.assertEqual(obj.prompt_slug, persisted_obj.prompt_slug)

    def test_exists(self):
        reminder_triggers = [
            ReminderTrigger(id=uuid.uuid4(), drill_instance_id=uuid.uuid4(), prompt_slug="slug-1"),
            ReminderTrigger(id=uuid.uuid4(), drill_instance_id=uuid.uuid4(), prompt_slug="slug-2"),
            ReminderTrigger(id=uuid.uuid4(), drill_instance_id=uuid.uuid4(), prompt_slug="slug-3"),
        ]
        self.repo.save_reminder_triggers(reminder_triggers)
        self.assertTrue(
            self.repo.reminder_trigger_exists(
                reminder_triggers[0].drill_instance_id, reminder_triggers[0].prompt_slug
            )
        )
        self.assertTrue(
            self.repo.reminder_trigger_exists(
                reminder_triggers[1].drill_instance_id, reminder_triggers[1].prompt_slug
            )
        )
        self.assertTrue(
            self.repo.reminder_trigger_exists(
                reminder_triggers[2].drill_instance_id, reminder_triggers[2].prompt_slug
            )
        )
        self.assertFalse(self.repo.reminder_trigger_exists(uuid.uuid4(), "slug-1"))
        self.assertFalse(
            self.repo.reminder_trigger_exists(
                reminder_triggers[0].drill_instance_id, "random-slug-1"
            )
        )

    def test_idempotent(self):
        reminder_trigger = ReminderTrigger(
            id=uuid.uuid4(), drill_instance_id=uuid.uuid4(), prompt_slug="slug-1"
        )
        self.assertFalse(
            self.repo.reminder_trigger_exists(
                reminder_trigger.drill_instance_id, reminder_trigger.prompt_slug
            )
        )
        self.repo.save_reminder_triggers([reminder_trigger])
        self.assertTrue(
            self.repo.reminder_trigger_exists(
                reminder_trigger.drill_instance_id, reminder_trigger.prompt_slug
            )
        )
        self.repo.save_reminder_triggers([reminder_trigger])
        self.assertTrue(
            self.repo.reminder_trigger_exists(
                reminder_trigger.drill_instance_id, reminder_trigger.prompt_slug
            )
        )
