import os
import unittest
import uuid
from unittest.mock import patch, MagicMock

from stopcovid.status.initiation import trigger_next_drills
from stopcovid.status.users import DrillProgress


class TestInitiation(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["STAGE"] = "test"

    def test_trigger_next_drills(self):
        with patch(
            "stopcovid.status.initiation.UserRepository.get_progress_for_users_who_need_drills",
            return_value=[
                DrillProgress(
                    phone_number="123456789",
                    user_id=uuid.uuid4(),
                    first_incomplete_drill_slug="01-basics",
                    first_unstarted_drill_slug="01-basics",
                ),
                DrillProgress(
                    phone_number="987654321",
                    user_id=uuid.uuid4(),
                    first_incomplete_drill_slug="02-prevention",
                    first_unstarted_drill_slug=None,
                ),
            ],
        ):
            with patch("stopcovid.event_distributor.initiation.boto3.client") as boto3_mock:
                kinesis_mock = MagicMock
                boto3_mock.return_value = kinesis_mock
                put_records_mock = MagicMock()
                kinesis_mock.put_records = put_records_mock
                trigger_next_drills()
                self.assertEqual(1, put_records_mock.call_count)
                kwargs = put_records_mock.call_args[1]
                self.assertEqual(2, len(kwargs["Records"]))
                self.assertEqual("command-stream-test", kwargs["StreamName"])

    def test_publish_none(self):
        with patch(
            "stopcovid.status.initiation.UserRepository.get_progress_for_users_who_need_drills",
            return_value=[],
        ):
            with patch("stopcovid.event_distributor.initiation.boto3.client") as boto3_mock:
                kinesis_mock = MagicMock
                boto3_mock.return_value = kinesis_mock
                put_records_mock = MagicMock()
                kinesis_mock.put_records = put_records_mock
                trigger_next_drills()
                self.assertEqual(0, put_records_mock.call_count)
