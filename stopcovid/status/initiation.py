import datetime
import json
import os
from typing import Iterable, Tuple, List

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
        self._publish_start_drill_commands(
            (drill_progress.phone_number, get_drill(drill_progress.next_drill_slug_to_trigger()))
            for drill_progress in repo.get_progress_for_users_who_need_drills(
                INACTIVITY_THRESHOLD_MINUTES
            )
        )

    def trigger_first_drill(self, phone_numbers: List[str]):
        if not phone_numbers:
            return
        self._publish_start_drill_commands(
            (phone_number, FIRST_DRILL) for phone_number in phone_numbers
        )

    def _get_kinesis_client(self):
        return boto3.client("kinesis")

    def _publish_start_drill_commands(self, drills: Iterable[Tuple[str, Drill]]):
        drills = [
            (phone_number, drill)
            for (phone_number, drill) in drills
            if not self._was_recently_initiated(phone_number, drill.slug)
        ]
        if not drills:
            return
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
        for phone_number, drill in drills:
            self._record_initiation(phone_number, drill.slug)

    def _was_recently_initiated(self, phone_number: str, drill_slug: str) -> bool:
        response = self.dynamodb.get_item(
            TableName=self._table_name(),
            Key={"phone_number": {"S": phone_number}, "drill_slug": {"S": drill_slug}},
        )
        return "Item" in response

    def _record_initiation(self, phone_number: str, drill_slug: str):
        self.dynamodb.put_item(
            TableName=self._table_name(),
            Item=dynamodb_utils.serialize(
                {
                    "phone_number": phone_number,
                    "drill_slug": drill_slug,
                    "expiration_ts": int(
                        (
                            datetime.datetime.now(datetime.timezone.utc)
                            + datetime.timedelta(hours=1)
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
                    {"AttributeName": "drill_slug", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "phone_number", "AttributeType": "S"},
                    {"AttributeName": "drill_slug", "AttributeType": "S"},
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
