import logging
import random

import boto3
import os
import json

from typing import Iterable
from stopcovid.drill_progress.drill_progress import DrillProgress


def publish_drills_to_trigger(
    drill_progresses: Iterable[DrillProgress], distribute_over_minutes: int
):
    if not drill_progresses:
        logging.info("No drills to trigger")
        return

    sqs = boto3.resource("sqs")

    queue_name = f"drill-initiation-{os.getenv('STAGE')}"
    queue = sqs.get_queue_by_name(QueueName=queue_name)

    for drill_progress in drill_progresses:
        delay_seconds = random.randint(1, distribute_over_minutes * 60)
        logging.info(f"Scheduling to run in {delay_seconds}s: {drill_progress}")
        queue.send_message(
            MessageBody=json.dumps(
                {
                    "idempotency_key": f"scheduled-{drill_progress.next_drill_slug_to_trigger()}",
                    "drill_progress": drill_progress.to_dict(),
                }
            ),
            DelaySeconds=delay_seconds,
        )
