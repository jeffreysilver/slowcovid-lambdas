import os
import unittest
from typing import List
from unittest.mock import patch, MagicMock

from stopcovid.dialog.dialog import UserValidated, DrillStarted
from stopcovid.dialog.registration import CodeValidationPayload
from stopcovid.dialog.types import UserProfile, DialogEvent
from stopcovid.drills.drills import Drill, Prompt
from stopcovid.event_distributor.initiation import trigger_initiation_if_needed


class TestInitiation(unittest.TestCase):
    def setUp(self) -> None:
        self.phone_number = "123456789"
        self.user_profile = UserProfile(validated=True)
        self.user_validated = UserValidated(
            self.phone_number,
            user_profile=self.user_profile,
            code_validation_payload=CodeValidationPayload(valid=True),
        )
        self.drill_started = DrillStarted(
            self.phone_number,
            user_profile=self.user_profile,
            drill=Drill(slug="test", name="test", prompts=[]),
            first_prompt=Prompt(slug="test", messages=["foo"]),
        )
        os.environ["STAGE"] = "test"

    def test_publish(self):
        events = [self.user_validated, self.drill_started, self.user_validated]
        with patch("stopcovid.event_distributor.initiation.boto3.client") as boto3_mock:
            kinesis_mock = MagicMock
            boto3_mock.return_value = kinesis_mock
            put_records_mock = MagicMock()
            kinesis_mock.put_records = put_records_mock
            trigger_initiation_if_needed(events)
            self.assertEqual(1, put_records_mock.call_count)
            kwargs = put_records_mock.call_args[1]
            self.assertEqual(2, len(kwargs["Records"]))
            self.assertEqual("command-stream-test", kwargs["StreamName"])

    def test_publish_none(self):
        events: List[DialogEvent] = [self.drill_started]
        with patch("stopcovid.event_distributor.initiation.boto3.client") as boto3_mock:
            kinesis_mock = MagicMock
            boto3_mock.return_value = kinesis_mock
            put_records_mock = MagicMock()
            kinesis_mock.put_records = put_records_mock
            trigger_initiation_if_needed(events)
            self.assertEqual(0, put_records_mock.call_count)
