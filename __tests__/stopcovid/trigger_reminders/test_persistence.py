import unittest
import uuid


from stopcovid import db
from stopcovid.trigger_reminders.persistence import ReminderTriggerRepository
from __tests__.utils.factories import make_drill_instance


class TestReminderTriggerRepo(unittest.TestCase):
    def setUp(self):
        self.repo = ReminderTriggerRepository(db.get_test_sqlalchemy_engine)
        self.repo.drop_and_recreate_tables_testing_only()

    def test_bulk_create_and_select(self):
        drills = [
            make_drill_instance(drill_instance_id=uuid.uuid4(), current_prompt_slug="slug-1"),
            make_drill_instance(drill_instance_id=uuid.uuid4(), current_prompt_slug="slug-2"),
            make_drill_instance(drill_instance_id=uuid.uuid4(), current_prompt_slug="slug-3"),
        ]

        self.repo.save_reminder_triggers_for_drills(drills)
        results = self.repo.get_reminder_triggers()
        self.assertEqual(len(results), 3)
        for obj, persisted_obj in zip(drills, results):
            self.assertEqual(obj.drill_instance_id, persisted_obj.drill_instance_id)
            self.assertEqual(obj.current_prompt_slug, persisted_obj.prompt_slug)

    def test_exists(self):
        drills = [
            make_drill_instance(drill_instance_id=uuid.uuid4(), current_prompt_slug="slug-1"),
            make_drill_instance(drill_instance_id=uuid.uuid4(), current_prompt_slug="slug-2"),
            make_drill_instance(drill_instance_id=uuid.uuid4(), current_prompt_slug="slug-3"),
        ]
        self.repo.save_reminder_triggers_for_drills(drills)
        self.assertTrue(
            self.repo.reminder_trigger_exists(
                drills[0].drill_instance_id, drills[0].current_prompt_slug
            )
        )
        self.assertTrue(
            self.repo.reminder_trigger_exists(
                drills[1].drill_instance_id, drills[1].current_prompt_slug
            )
        )
        self.assertTrue(
            self.repo.reminder_trigger_exists(
                drills[2].drill_instance_id, drills[2].current_prompt_slug
            )
        )
        self.assertFalse(self.repo.reminder_trigger_exists(uuid.uuid4(), "slug-1"))
        self.assertFalse(
            self.repo.reminder_trigger_exists(drills[0].drill_instance_id, "random-slug-1")
        )

    def test_idempotent(self):
        drill = make_drill_instance(drill_instance_id=uuid.uuid4(), current_prompt_slug="slug-1")
        self.assertFalse(
            self.repo.reminder_trigger_exists(drill.drill_instance_id, drill.current_prompt_slug)
        )
        self.repo.save_reminder_triggers_for_drills([drill])
        self.assertTrue(
            self.repo.reminder_trigger_exists(drill.drill_instance_id, drill.current_prompt_slug)
        )
        self.repo.save_reminder_triggers_for_drills([drill])
        self.assertTrue(
            self.repo.reminder_trigger_exists(drill.drill_instance_id, drill.current_prompt_slug)
        )
