import os
import unittest
import uuid
from unittest.mock import patch, MagicMock

from stopcovid.status.initiation import DrillInitiator
from stopcovid.status.users import DrillProgress


@patch("stopcovid.status.initiation.DrillInitiator._was_recently_initiated", return_value=False)
@patch("stopcovid.status.initiation.DrillInitiator._record_initiation")
@patch("stopcovid.status.initiation.DrillInitiator._get_kinesis_client")
class TestInitiation(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["STAGE"] = "test"
        self.initiator = DrillInitiator(
            region_name="us-west-2",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="fake-key",
            aws_secret_access_key="fake-secret",
        )
        self.kinesis_mock = MagicMock()
        self.put_records_mock = MagicMock()
        self.kinesis_mock.put_records = self.put_records_mock

    def test_trigger_next_drills(
        self, get_kinesis_mock, record_initiation_mock, recently_initiated_mock
    ):
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
            get_kinesis_mock.return_value = self.kinesis_mock
            self.initiator.trigger_next_drills()
            self.assertEqual(1, self.put_records_mock.call_count)
            kwargs = self.put_records_mock.call_args[1]
            self.assertEqual(2, len(kwargs["Records"]))
            self.assertEqual("command-stream-test", kwargs["StreamName"])

    def test_publish_none(self, get_kinesis_mock, record_initiation_mock, recently_initiated_mock):
        with patch(
            "stopcovid.status.initiation.UserRepository.get_progress_for_users_who_need_drills",
            return_value=[],
        ):
            get_kinesis_mock.return_value = self.kinesis_mock
            self.initiator.trigger_next_drills()
            self.assertEqual(0, self.put_records_mock.call_count)

    def test_trigger_first_drill(
        self, get_kinesis_mock, record_initiation_mock, recently_initiated_mock
    ):
        get_kinesis_mock.return_value = self.kinesis_mock
        self.initiator.trigger_first_drill(["123456789", "987654321"])
        self.assertEqual(1, self.put_records_mock.call_count)
        kwargs = self.put_records_mock.call_args[1]
        self.assertEqual(2, len(kwargs["Records"]))
        self.assertEqual("command-stream-test", kwargs["StreamName"])

    def test_trigger_first_drill_none(
        self, get_kinesis_mock, record_initiation_mock, recently_initiated_mock
    ):
        get_kinesis_mock.return_value = self.kinesis_mock
        self.initiator.trigger_first_drill([])
        self.assertEqual(0, self.put_records_mock.call_count)


class TestRecordInitiation(unittest.TestCase):
    def setUp(self):
        os.environ["STAGE"] = "test"
        self.initiator = DrillInitiator(
            region_name="us-west-2",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="fake-key",
            aws_secret_access_key="fake-secret",
        )
        self.initiator.ensure_tables_exist()

    def test_initiation(self):
        # we aren't erasing our DB between test runs, so let's ensure the phone number is unique
        phone_number = str(uuid.uuid4())
        slug1 = "a-slug"
        slug2 = "b-slug"
        self.assertFalse(self.initiator._was_recently_initiated(phone_number, slug1))
        self.assertFalse(self.initiator._was_recently_initiated(phone_number, slug2))

        self.initiator._record_initiation(phone_number, slug1)
        self.assertTrue(self.initiator._was_recently_initiated(phone_number, slug1))
        self.assertFalse(self.initiator._was_recently_initiated(phone_number, slug2))
