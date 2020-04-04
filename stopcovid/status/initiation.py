import datetime
import json
import os
import uuid
from typing import Iterable, Tuple

import boto3
from stopcovid.utils import dynamodb as dynamodb_utils

from .users import UserRepository
from ..drills.drills import get_drill, Drill

INACTIVITY_THRESHOLD_MINUTES = 720
FIRST_DRILL = get_drill("01-basics")


class DrillInitiator:
    def __init__(self, **kwargs):
        self.dynamodb = boto3.client("dynamodb", **kwargs)
        self.stage = os.environ.get("STAGE")

    def trigger_next_drills(self):
        repo = UserRepository()
        drill_progresses = repo.get_progress_for_users_who_need_drills(INACTIVITY_THRESHOLD_MINUTES)
        to_trigger = []
        for drill_progress in drill_progresses:
            if not self._was_recently_initiated(
                drill_progress.phone_number,
                drill_progress.next_drill_slug_to_trigger(),
                "scheduled",
            ):
                to_trigger.append(drill_progress)

        if not to_trigger:
            return

        self._publish_start_drill_commands(
            (drill_progress.phone_number, get_drill(drill_progress.next_drill_slug_to_trigger()))
            for drill_progress in to_trigger
        )
        for drill_progress in to_trigger:
            self._record_initiation(
                drill_progress.phone_number,
                drill_progress.next_drill_slug_to_trigger(),
                "scheduled",
            )

    def trigger_first_drill(self, phone_number: str, idempotency_key: str):
        if not self._was_recently_initiated(phone_number, FIRST_DRILL.slug, idempotency_key):
            self._publish_start_drill_commands([(phone_number, FIRST_DRILL)])
        self._record_initiation(phone_number, FIRST_DRILL.slug, idempotency_key)

    def trigger_next_drill_for_user(
        self, user_id: uuid.UUID, phone_number: str, idempotency_key: str
    ):
        repo = UserRepository()
        drill_progress = repo.get_progress_for_user(user_id, phone_number)
        slug = drill_progress.next_drill_slug_to_trigger()
        if not self._was_recently_initiated(phone_number, slug, idempotency_key):
            self._publish_start_drill_commands([(phone_number, get_drill(slug))])
        self._record_initiation(phone_number, slug, idempotency_key)

    def _get_kinesis_client(self):
        return boto3.client("kinesis")

    def _publish_start_drill_commands(self, drills: Iterable[Tuple[str, Drill]]):
        kinesis = self._get_kinesis_client()
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
        kinesis.put_records(Records=records, StreamName=f"command-stream-{self.stage}")

    def _was_recently_initiated(
        self, phone_number: str, drill_slug: str, idempotency_key: str
    ) -> bool:
        response = self.dynamodb.get_item(
            TableName=self._table_name(),
            Key={
                "phone_number": {"S": phone_number},
                "idempotency_key": {"S": f"{drill_slug}-{idempotency_key}"},
            },
        )
        return "Item" in response

    def _record_initiation(self, phone_number: str, drill_slug: str, idempotency_key: str):
        self.dynamodb.put_item(
            TableName=self._table_name(),
            Item=dynamodb_utils.serialize(
                {
                    "phone_number": phone_number,
                    "idempotency_key": f"{drill_slug}-{idempotency_key}",
                    "expiration_ts": int(
                        (
                            datetime.datetime.now(datetime.timezone.utc)
                            + datetime.timedelta(hours=10)
                        ).timestamp()
                    ),
                }
            ),
        )

    def _table_name(self) -> str:
        return f"drill-initiations-{self.stage}"

    def ensure_tables_exist(self):
        try:
            self.dynamodb.create_table(
                TableName=self._table_name(),
                KeySchema=[
                    {"AttributeName": "phone_number", "KeyType": "HASH"},
                    {"AttributeName": "idempotency_key", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "phone_number", "AttributeType": "S"},
                    {"AttributeName": "idempotency_key", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            self.dynamodb.update_time_to_live(
                TableName=self._table_name(),
                TimeToLiveSpecification={"AttributeName": "expiration_ts", "Enabled": True},
            )
        except Exception:
            # table already exists, most likely
            pass
