import json
import os
from typing import Iterator

import boto3

from stopcovid.drills.drills import get_drill
from stopcovid.status.users import UserRepository, DrillProgress

INACTIVITY_THRESHOLD_MINUTES = 721


def handler(event, context):
    repo = UserRepository()
    _publish_start_drill_commands(
        repo.get_progress_for_users_who_need_drills(INACTIVITY_THRESHOLD_MINUTES)
    )

    return {"statusCode": 200}


def _publish_start_drill_commands(drill_progress_statuses: Iterator[DrillProgress]):
    kinesis = boto3.client("kinesis")
    records = [
        {
            "Data": json.dumps(
                {
                    "type": "START_DRILL",
                    "payload": {
                        "phone_number": drill_progress.phone_number,
                        "drill": get_drill(
                            drill_progress.first_unstarted_drill_slug
                            if drill_progress.first_unstarted_drill_slug is not None
                            else drill_progress.first_incomplete_drill_slug
                        ).to_dict(),
                    },
                }
            ),
            "PartitionKey": drill_progress.phone_number,
        }
        for drill_progress in drill_progress_statuses
    ]
    if records:
        stage = os.environ.get("STAGE")
        kinesis.put_records(Records=records, StreamName=f"command-stream-{stage}")
