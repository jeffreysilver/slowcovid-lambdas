import unittest
import uuid
import datetime
from stopcovid.status import db
from stopcovid.status.drill_instances import DrillInstanceRepository, DrillInstance


class TestDrillInstances(unittest.TestCase):
    def setUp(self):
        self.repo = DrillInstanceRepository(db.get_test_sqlalchemy_engine)
        self.repo.drop_and_recreate_tables_testing_only()

    def test_get_and_save(self):
        drill_instance = DrillInstance(
            drill_instance_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            drill_slug="test",
            current_prompt_slug="test-prompt",
            current_prompt_start_time=datetime.datetime.now(),
            current_prompt_last_response_time=datetime.datetime.now(),
            is_complete=False,
            is_valid=True,
        )
        self.assertIsNone(self.repo.get_drill_instance(drill_instance.drill_instance_id))
        self.repo.save_drill_instance(drill_instance)
        retrieved = self.repo.get_drill_instance(drill_instance.drill_instance_id)
        self.assertEqual(drill_instance, retrieved)
        drill_instance.is_complete = True
        self.repo.save_drill_instance(drill_instance)
        retrieved = self.repo.get_drill_instance(drill_instance.drill_instance_id)
        self.assertEqual(drill_instance, retrieved)
