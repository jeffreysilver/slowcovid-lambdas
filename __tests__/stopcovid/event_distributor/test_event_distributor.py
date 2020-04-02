import unittest
from unittest.mock import patch, MagicMock
import json

from stopcovid.event_distributor.event_distributor import distribute_dialog_events


class TestHandleCommand(unittest.TestCase):
    def _get_mocked_send_messages(self, boto_mock):
        sqs_mock = MagicMock()
        boto_mock.resource.return_value = sqs_mock
        queue = MagicMock(name="queue")
        send_messages_mock = MagicMock()
        queue.send_messages = send_messages_mock
        sqs_mock.get_queue_by_name = MagicMock(return_value=queue)
        return send_messages_mock

    @patch("stopcovid.clients.sqs.boto3")
    def test_distribute_events(self, boto_mock):
        send_messages_mock = self._get_mocked_send_messages(boto_mock)

        with open("sample_events/distribute_event.json") as f:
            mock_event = json.load(f)
        distribute_dialog_events(mock_event, None)

        send_messages_mock.assert_called_once()
        call = send_messages_mock.mock_calls[0]
        _, *kwargs = call

        entries = kwargs[1]["Entries"]
        self.assertEqual(len(entries), 1)
