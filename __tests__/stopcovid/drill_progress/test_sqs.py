import logging
import unittest
import uuid
from unittest.mock import patch, MagicMock

from stopcovid.drill_progress.drill_progress import DrillProgress
from stopcovid.drill_progress.sqs import publish_drills_to_trigger


@patch("stopcovid.drill_progress.sqs.boto3")
class TestEnqueueOutboundDrillsToTrigger(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)

    def _get_mocked_send_message(self, boto_mock):
        sqs_mock = MagicMock()
        boto_mock.resource.return_value = sqs_mock
        queue = MagicMock(name="queue")
        send_message_mock = MagicMock()
        queue.send_message = send_message_mock
        sqs_mock.get_queue_by_name = MagicMock(return_value=queue)
        return send_message_mock

    def test_publish_drills_to_trigger(self, boto_mock):
        send_message_mock = self._get_mocked_send_message(boto_mock)

        drill_progresses = [
            DrillProgress(
                phone_number="123456789",
                user_id=uuid.uuid4(),
                first_unstarted_drill_slug="first",
                first_incomplete_drill_slug="second",
            ),
            DrillProgress(
                phone_number="987654321",
                user_id=uuid.uuid4(),
                first_unstarted_drill_slug="first",
                first_incomplete_drill_slug="second",
            ),
        ]
        publish_drills_to_trigger(drill_progresses, 2)
        self.assertEqual(2, send_message_mock.call_count)
        delay_seconds_0 = send_message_mock.call_args_list[0][1]["DelaySeconds"]
        self.assertTrue(1 <= delay_seconds_0 <= 120)
        delay_seconds_1 = send_message_mock.call_args_list[1][1]["DelaySeconds"]
        self.assertTrue(1 <= delay_seconds_1 <= 120)
