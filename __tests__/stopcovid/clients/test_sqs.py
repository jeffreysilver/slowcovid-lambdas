import unittest
from unittest.mock import patch, MagicMock
import json
import uuid
from stopcovid.event_distributor.outbound_sms import OutboundSMS
from stopcovid.clients.sqs import publish_outbound_sms_messages


@patch("stopcovid.clients.sqs.boto3")
class TestPublishOutboundSMS(unittest.TestCase):
    def _get_mocked_send_messages(self, boto_mock):
        sqs_mock = MagicMock()
        boto_mock.resource.return_value = sqs_mock
        queue = MagicMock(name="queue")
        send_messages_mock = MagicMock()
        queue.send_messages = send_messages_mock
        sqs_mock.get_queue_by_name = MagicMock(return_value=queue)
        return send_messages_mock

    def _get_send_message_entries(self, send_messages_mock):
        send_messages_mock.assert_called_once()
        call = send_messages_mock.mock_calls[0]
        _, *kwargs = call
        return kwargs[1]["Entries"]

    def test_no_messages(self, boto_mock):
        send_messages_mock = self._get_mocked_send_messages(boto_mock)
        publish_outbound_sms_messages([])
        send_messages_mock.assert_not_called()

    def test_sends_messages_to_one_phone_number_for_one_event(self, boto_mock):
        send_messages_mock = self._get_mocked_send_messages(boto_mock)
        phone_number = "+15551234321"

        event_id = uuid.uuid4()
        messages = [
            OutboundSMS(event_id=event_id, phone_number=phone_number, body="message 1"),
            OutboundSMS(event_id=event_id, phone_number=phone_number, body="message 2"),
            OutboundSMS(event_id=event_id, phone_number=phone_number, body="message 3"),
        ]

        publish_outbound_sms_messages(messages)
        entries = self._get_send_message_entries(send_messages_mock)

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["MessageDeduplicationId"], str(event_id))
        self.assertEqual(
            entry["MessageBody"],
            json.dumps(
                {
                    "phone_number": phone_number,
                    "messages": [
                        {"body": "message 1", "media_url": None},
                        {"body": "message 2", "media_url": None},
                        {"body": "message 3", "media_url": None},
                    ],
                }
            ),
        )
        self.assertEqual(entry["MessageGroupId"], phone_number)

    def test_sends_messages_to_one_phone_number_for_multiple_events(self, boto_mock):
        send_messages_mock = self._get_mocked_send_messages(boto_mock)
        phone_number = "+15551234321"

        event_1_id = uuid.uuid4()
        event_2_id = uuid.uuid4()
        messages = [
            OutboundSMS(event_id=event_1_id, phone_number=phone_number, body="message 1"),
            OutboundSMS(event_id=event_1_id, phone_number=phone_number, body="message 2"),
            OutboundSMS(event_id=event_2_id, phone_number=phone_number, body="message 3"),
        ]

        publish_outbound_sms_messages(messages)
        entries = self._get_send_message_entries(send_messages_mock)

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertIn(str(event_1_id), entry["MessageDeduplicationId"])
        self.assertIn(str(event_2_id), entry["MessageDeduplicationId"])
        self.assertEqual(
            entry["MessageBody"],
            json.dumps(
                {
                    "phone_number": phone_number,
                    "messages": [
                        {"body": "message 1", "media_url": None},
                        {"body": "message 2", "media_url": None},
                        {"body": "message 3", "media_url": None},
                    ],
                }
            ),
        )
        self.assertEqual(entry["MessageGroupId"], phone_number)

    def test_sends_messages_to_multiple_phone_numbers_for_one_event_each(self, boto_mock):
        send_messages_mock = self._get_mocked_send_messages(boto_mock)
        phone_number_1 = "+15551234321"
        phone_number_2 = "+15559998888"
        event_1_id = uuid.uuid4()
        event_2_id = uuid.uuid4()

        messages = [
            OutboundSMS(event_id=event_1_id, phone_number=phone_number_1, body="message 1"),
            OutboundSMS(event_id=event_1_id, phone_number=phone_number_1, body="message 2"),
            OutboundSMS(event_id=event_2_id, phone_number=phone_number_2, body="message 3"),
        ]

        publish_outbound_sms_messages(messages)
        entries = self._get_send_message_entries(send_messages_mock)

        self.assertEqual(len(entries), 2)

        # first entry
        entry = entries[0]
        self.assertIn(str(event_1_id), entry["MessageDeduplicationId"])
        self.assertEqual(
            entry["MessageBody"],
            json.dumps(
                {
                    "phone_number": phone_number_1,
                    "messages": [
                        {"body": "message 1", "media_url": None},
                        {"body": "message 2", "media_url": None},
                    ],
                }
            ),
        )
        self.assertEqual(entry["MessageGroupId"], phone_number_1)

        # second entry
        entry = entries[1]
        self.assertIn(str(event_2_id), entry["MessageDeduplicationId"])
        self.assertEqual(
            entry["MessageBody"],
            json.dumps(
                {
                    "phone_number": phone_number_2,
                    "messages": [{"body": "message 3", "media_url": None}],
                }
            ),
        )
        self.assertEqual(entry["MessageGroupId"], phone_number_2)

    def test_sends_messages_to_multiple_phone_numbers_for_multiple_events_each(self, boto_mock):
        send_messages_mock = self._get_mocked_send_messages(boto_mock)
        phone_number_1 = "+15551234321"
        phone_number_2 = "+15559998888"
        phone_number_3 = "+15551110000"

        phone_number_1_event_ids = [uuid.uuid4(), uuid.uuid4()]
        phone_number_2_event_ids = [uuid.uuid4(), uuid.uuid4()]
        phone_number_3_event_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

        messages = [
            OutboundSMS(
                event_id=phone_number_1_event_ids[0], phone_number=phone_number_1, body="message 1"
            ),
            OutboundSMS(
                event_id=phone_number_1_event_ids[1], phone_number=phone_number_1, body="message 2"
            ),
            OutboundSMS(
                event_id=phone_number_2_event_ids[0], phone_number=phone_number_2, body="message 3"
            ),
            OutboundSMS(
                event_id=phone_number_2_event_ids[1], phone_number=phone_number_2, body="message 4"
            ),
            OutboundSMS(
                event_id=phone_number_3_event_ids[0], phone_number=phone_number_3, body="message 5"
            ),
            OutboundSMS(
                event_id=phone_number_3_event_ids[1], phone_number=phone_number_3, body="message 6"
            ),
            OutboundSMS(
                event_id=phone_number_3_event_ids[2], phone_number=phone_number_3, body="message 7"
            ),
        ]

        publish_outbound_sms_messages(messages)
        entries = self._get_send_message_entries(send_messages_mock)

        self.assertEqual(len(entries), 3)

        # first entry
        entry = entries[0]
        for event_id in phone_number_1_event_ids:
            self.assertIn(str(event_id), entry["MessageDeduplicationId"])

        self.assertEqual(
            entry["MessageBody"],
            json.dumps(
                {
                    "phone_number": phone_number_1,
                    "messages": [
                        {"body": "message 1", "media_url": None},
                        {"body": "message 2", "media_url": None},
                    ],
                }
            ),
        )
        self.assertEqual(entry["MessageGroupId"], phone_number_1)

        # second entry
        entry = entries[1]
        for event_id in phone_number_2_event_ids:
            self.assertIn(str(event_id), entry["MessageDeduplicationId"])

        self.assertEqual(
            entry["MessageBody"],
            json.dumps(
                {
                    "phone_number": phone_number_2,
                    "messages": [
                        {"body": "message 3", "media_url": None},
                        {"body": "message 4", "media_url": None},
                    ],
                }
            ),
        )
        self.assertEqual(entry["MessageGroupId"], phone_number_2)

        # third entry
        entry = entries[2]
        for event_id in phone_number_3_event_ids:
            self.assertIn(str(event_id), entry["MessageDeduplicationId"])

        self.assertEqual(
            entry["MessageBody"],
            json.dumps(
                {
                    "phone_number": phone_number_3,
                    "messages": [
                        {"body": "message 5", "media_url": None},
                        {"body": "message 6", "media_url": None},
                        {"body": "message 7", "media_url": None},
                    ],
                }
            ),
        )
        self.assertEqual(entry["MessageGroupId"], phone_number_3)
