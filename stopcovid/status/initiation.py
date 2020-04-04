import json
import os
from typing import Iterable, Tuple

import boto3

from .users import UserRepository
from ..drills.drills import get_drill, Drill

INACTIVITY_THRESHOLD_MINUTES = 720


def trigger_next_drills():
    repo = UserRepository()
    _publish_start_drill_commands(
        (drill_progress.phone_number, get_drill(drill_progress.next_drill_slug_to_trigger()))
        for drill_progress in repo.get_progress_for_users_who_need_drills(
            INACTIVITY_THRESHOLD_MINUTES
        )
    )


def _publish_start_drill_commands(drills: Iterable[Tuple[str, Drill]]):
    kinesis = boto3.client("kinesis")
    records = [
        {
            "Data": json.dumps(
                {
                    "type": "START_DRILL",
                    "payload": {"phone_number": phone_number, "drill": drill.to_dict()},
                }
            ),
            "PartitionKey": phone_number,
        }
        for phone_number, drill in drills
    ]
    if records:
        stage = os.environ.get("STAGE")
        kinesis.put_records(Records=records, StreamName=f"command-stream-{stage}")
