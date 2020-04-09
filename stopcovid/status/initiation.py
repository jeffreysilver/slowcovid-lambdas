import datetime
import logging
import os

import boto3
from stopcovid.utils import dynamodb as dynamodb_utils

from .drill_progress import DrillProgressRepository
from ..dialog.command_stream.publish import CommandPublisher

FIRST_DRILL_SLUG = "01-basics"


class DrillInitiator:
    def __init__(self, **kwargs):
        self.dynamodb = boto3.client("dynamodb", **kwargs)
        self.stage = os.environ.get("STAGE")

        self.drill_progress_repository = DrillProgressRepository()
        self.command_publisher = CommandPublisher()

    def trigger_first_drill(self, phone_number: str, idempotency_key: str):
        self.trigger_drill(phone_number, FIRST_DRILL_SLUG, idempotency_key)

    def trigger_next_drill_for_user(self, phone_number: str, idempotency_key: str):
        drill_progress = self.drill_progress_repository.get_progress_for_user(phone_number)
        drill_slug = drill_progress.next_drill_slug_to_trigger()
        self.trigger_drill(phone_number, drill_slug, idempotency_key)

    def trigger_drill_if_not_stale(self, phone_number: str, drill_slug: str, idempotency_key: str):
        drill_progress = self.drill_progress_repository.get_progress_for_user(phone_number)
        if drill_progress.next_drill_slug_to_trigger() != drill_slug:
            # the request is stale. Since it was enqueued, the user has started or
            # completed a drill.
            logging.info(
                f"Ignoring request to trigger {drill_slug} for {phone_number} because it is stale"
            )
            return
        self.trigger_drill(
            drill_progress.phone_number,
            drill_progress.next_drill_slug_to_trigger(),
            idempotency_key,
        )

    def trigger_drill(self, phone_number: str, drill_slug: str, idempotency_key: str):
        if not self._was_recently_initiated(phone_number, drill_slug, idempotency_key):
            self.command_publisher.publish_start_drill_command(phone_number, drill_slug)
            self._record_initiation(phone_number, drill_slug, idempotency_key)

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
