import unittest
from unittest.mock import patch
import json

from stopcovid.command_stream import handle_command
from stopcovid.dialog.dialog import ProcessSMSMessage, TriggerReminder, StartDrill


class TestHandleCommand(unittest.TestCase):
    @patch("stopcovid.command_stream.process_command")
    def test_inbound_sms(self, process_command_mock):
        with open("sample_events/inbound_sms_event.json") as f:
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

    @patch("stopcovid.command_stream.process_command")
    def test_trigger_reminder(self, process_command_mock):
        with open("sample_events/trigger_reminder_command.json") as f:
            mock_kinesis_event = json.load(f)

        handle_command(mock_kinesis_event, None)

        process_command_mock.assert_called_once()

        call = process_command_mock.call_args_list[0]
        args, _ = call

        command = args[0]
        self.assertTrue(isinstance(command, TriggerReminder))
        self.assertEqual(command.prompt_slug, "hand-washing")
        self.assertEqual(command.drill_id, "1234-1234-1234-1234")

        self.assertEqual(args[1], mock_kinesis_event["Records"][0]["kinesis"]["sequenceNumber"])

    @patch("stopcovid.command_stream.process_command")
    def test_start_drill(self, process_command_mock):
        with open("sample_events/start_drill_command.json") as f:
            mock_kinesis_event = json.load(f)

        handle_command(mock_kinesis_event, None)

        process_command_mock.assert_called_once()

        call = process_command_mock.call_args_list[0]
        args, _ = call

        command = args[0]
        self.assertTrue(isinstance(command, StartDrill))

        self.assertEqual(command.drill.name, "Hand washing")
        self.assertEqual(len(command.drill.prompts), 1)
        prompt = command.drill.prompts[0]
        self.assertEqual(prompt.slug, "hand-washing")
        self.assertEqual(prompt.messages, ["a) hello", "b) how are you?"])
        self.assertEqual(prompt.correct_response, "a) hello")

        self.assertEqual(args[1], mock_kinesis_event["Records"][0]["kinesis"]["sequenceNumber"])

    @patch("stopcovid.command_stream.process_command")
    def test_unknown_command(self, process_command_mock):
        with open("sample_events/unknown_command.json") as f:
            mock_kinesis_event = json.load(f)

        with self.assertRaises(RuntimeError):
            handle_command(mock_kinesis_event, None)
