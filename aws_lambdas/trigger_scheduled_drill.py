import json
from typing import Dict

from stopcovid.status.initiation import DrillInitiator
from stopcovid.status.drill_progress import DrillProgressSchema, DrillProgress

from stopcovid.utils.logging import configure_logging

configure_logging()


def handler(event, context):
    items = [json.loads(record["body"]) for record in event["Records"]]
    drill_progresses_to_schedule: Dict[str, DrillProgress] = {
        item["idempotency_key"]: DrillProgressSchema().load(item["drill_progress"])
        for item in items
    }
    initiator = DrillInitiator()

    for idempotency_key, drill_progress in drill_progresses_to_schedule.items():
        initiator.trigger_drill_if_not_stale(
            drill_progress.phone_number,
            drill_progress.next_drill_slug_to_trigger(),
            idempotency_key,
        )

    return {"statusCode": 200}
