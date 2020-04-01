# thank you sir, may I have another?
import json
import os
from typing import List

import boto3

from stopcovid.dialog.dialog import UserValidated
from stopcovid.dialog.types import DialogEvent
from stopcovid.drills.drills import get_drill

FIRST_DRILL = get_drill("01-basics").to_dict()


def trigger_initiation_if_needed(dialog_events: List[DialogEvent]):
    phone_numbers = [
        event.phone_number for event in dialog_events if isinstance(event, UserValidated)
    ]
    if phone_numbers:
        _publish_start_drill_commands(phone_numbers)


def _publish_start_drill_commands(phone_numbers: List[str]):
    kinesis = boto3.client("kinesis")
    records = [
        {
            "Data": json.dumps(
                {
                    "type": "START_DRILL",
                    "payload": {"phone_number": phone_number, "drill": FIRST_DRILL},
                }
            ),
            "PartitionKey": phone_number,
        }
        for phone_number in phone_numbers
    ]
    stage = os.environ.get("STAGE")
    kinesis.put_records(Records=records, StreamName=f"command-stream-{stage}")
