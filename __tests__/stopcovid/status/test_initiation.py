import os
import unittest
import uuid
from unittest.mock import patch

from stopcovid.status.initiation import DrillInitiator, FIRST_DRILL_SLUG
from stopcovid.status.drill_progress import DrillProgress


@patch("stopcovid.dialog.command_stream.publish.CommandPublisher.publish_start_drill_command")
class TestInitiation(unittest.TestCase):
    def setUp(self):
        os.environ["STAGE"] = "test"
        self.initiator = DrillInitiator(
            region_name="us-west-2",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="fake-key",
            aws_secret_access_key="fake-secret",
        )
        self.initiator.ensure_tables_exist()

    def test_initiation_first_drill(self, publish_mock):
        # we aren't erasing our DB between test runs, so let's ensure the phone number is unique
        phone_number = str(uuid.uuid4())
        idempotency_key = str(uuid.uuid4())

        self.initiator.trigger_first_drill(phone_number, idempotency_key)
        publish_mock.assert_called_once_with(phone_number, FIRST_DRILL_SLUG)
        publish_mock.reset_mock()
        self.initiator.trigger_first_drill(phone_number, idempotency_key)
        publish_mock.assert_not_called()

    def test_initiation_next_drill_for_user(self, publish_mock):
        phone_number = str(uuid.uuid4())
        user_id = uuid.uuid4()
        idempotency_key = str(uuid.uuid4())
        with patch(
            "stopcovid.status.initiation.DrillProgressRepository.get_progress_for_user",
            return_value=DrillProgress(
                phone_number=phone_number,
                user_id=user_id,
                first_incomplete_drill_slug="02-prevention",
                first_unstarted_drill_slug="03-hand-washing-how",
            ),
        ):
            self.initiator.trigger_next_drill_for_user(user_id, phone_number, idempotency_key)
            publish_mock.assert_called_once_with(phone_number, "03-hand-washing-how")
            publish_mock.reset_mock()
            self.initiator.trigger_next_drill_for_user(user_id, phone_number, idempotency_key)
            publish_mock.assert_not_called()

    def test_trigger_drill_if_not_stale(self, publish_mock):
        phone_number = str(uuid.uuid4())
        user_id = uuid.uuid4()

        with patch(
            "stopcovid.status.initiation.DrillProgressRepository.get_progress_for_user",
            return_value=DrillProgress(
                phone_number=phone_number,
                user_id=user_id,
                first_incomplete_drill_slug="02-prevention",
                first_unstarted_drill_slug="03-hand-washing-how",
            ),
        ):
            self.initiator.trigger_drill_if_not_stale(user_id, phone_number, "01-basics", "foo")
            publish_mock.assert_not_called()
            self.initiator.trigger_drill_if_not_stale(
                user_id, phone_number, "03-hand-washing-how", str(uuid.uuid4())
            )
            publish_mock.assert_called_once_with(phone_number, "03-hand-washing-how")

    def test_trigger_drill(self, publish_mock):
        phone_number = str(uuid.uuid4())
        slug = "02-prevention"
        idempotency_key = str(uuid.uuid4())
        self.initiator.trigger_drill(phone_number, slug, idempotency_key)
        publish_mock.assert_called_once_with(phone_number, slug)
        publish_mock.reset_mock()
        self.initiator.trigger_drill(phone_number, slug, idempotency_key)
        publish_mock.assert_not_called()
