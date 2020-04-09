import logging
import os
import unittest
from unittest.mock import patch
import json
import uuid

from aws_lambdas.handle_command import handler as handle_command
from stopcovid.dialog.engine import StartDrill, TriggerReminder, ProcessSMSMessage

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


@patch("stopcovid.dialog.command_stream.command_stream.process_command")
class TestHandleCommand(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.CRITICAL)

    def test_inbound_sms(self, process_command_mock):
        with open(os.path.join(__location__, "../../../sample_events/inbound_sms_event.json")) as f:
            mock_kinesis_event = json.load(f)

        handle_command(mock_kinesis_event, None)

        process_command_mock.assert_called_once()

        call = process_command_mock.call_args_list[0]
        args, _ = call

        command = args[0]
        self.assertTrue(isinstance(command, ProcessSMSMessage))
        self.assertEqual(command.phone_number, "+14802865415")
        self.assertEqual(command.content, "🤡")

        self.assertEqual(args[1], mock_kinesis_event["Records"][0]["kinesis"]["sequenceNumber"])

    def test_trigger_reminder(self, process_command_mock):
        with open(
            os.path.join(__location__, "../../../sample_events/trigger_reminder_command.json")
        ) as f:
            mock_kinesis_event = json.load(f)

        handle_command(mock_kinesis_event, None)

        process_command_mock.assert_called_once()

        call = process_command_mock.call_args_list[0]
        args, _ = call

        command = args[0]
        self.assertTrue(isinstance(command, TriggerReminder))
        self.assertEqual(command.prompt_slug, "hand-washing")

        self.assertEqual(
            command.drill_instance_id, uuid.UUID("2e34a300-a9f3-47bd-9a41-005561f0532e")
        )

        self.assertEqual(args[1], mock_kinesis_event["Records"][0]["kinesis"]["sequenceNumber"])

    def test_start_drill(self, process_command_mock):
        with open(
            os.path.join(__location__, "../../../sample_events/start_drill_command.json")
        ) as f:
            mock_kinesis_event = json.load(f)

        handle_command(mock_kinesis_event, None)

        process_command_mock.assert_called_once()

        call = process_command_mock.call_args_list[0]
        args, _ = call

        command = args[0]
        self.assertTrue(isinstance(command, StartDrill))
        self.assertTrue("hand-washing", command.drill_slug)
        self.assertEqual(args[1], mock_kinesis_event["Records"][0]["kinesis"]["sequenceNumber"])

    def test_unknown_command(self, process_command_mock):
        with open(os.path.join(__location__, "../../../sample_events/unknown_command.json")) as f:
            mock_kinesis_event = json.load(f)

        with self.assertRaises(RuntimeError):
            handle_command(mock_kinesis_event, None)
