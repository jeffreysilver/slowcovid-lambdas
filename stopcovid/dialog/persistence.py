import os
import uuid
from abc import ABC, abstractmethod
from typing import List

import boto3

from stopcovid.utils import dynamodb as dynamodb_utils
from .types import DialogState, DialogEvent, DialogStateSchema


class DialogRepository(ABC):
    @abstractmethod
    def fetch_dialog_state(self, phone_number: str) -> DialogState:
        pass

    @abstractmethod
    def persist_dialog_state(self, events: List[DialogEvent], dialog_state: DialogState):
        pass


class DynamoDBDialogRepository(DialogRepository):
    def __init__(self, table_name_suffix=None, **kwargs):
        self.dynamodb = boto3.client("dynamodb", **kwargs)
        if table_name_suffix is None:
            table_name_suffix = os.getenv("DIALOG_TABLE_NAME_SUFFIX", "")
        self.table_name_suffix = table_name_suffix

    def events_table_name(self):
        return (
            f"dialog-events-{self.table_name_suffix}" if self.table_name_suffix else "dialog-events"
        )

    def state_table_name(self):
        return (
            f"dialog-state-{self.table_name_suffix}" if self.table_name_suffix else "dialog-state"
        )

    def fetch_dialog_state(self, phone_number: str) -> DialogState:
        response = self.dynamodb.get_item(
            TableName=self.state_table_name(),
            Key={"phone_number": {"S": phone_number}},
            ConsistentRead=True,
        )
        if "Item" not in response:
            return DialogState(phone_number=phone_number, seq="0")
        dialog_dict = dynamodb_utils.deserialize(response["Item"])
        return DialogStateSchema().load(dialog_dict)

    def fetch_dialog_event(self, phone_number: str, event_id: uuid.UUID) -> DialogEvent:
        response = self.dynamodb.get_item(
            TableName=self.events_table_name(),
            Key={"phone_number": {"S": phone_number}, "event_id": {"S": str(event_id)}},
            ConsistentRead=True,
        )
        dialog_dict = dynamodb_utils.deserialize(response['Item'])
        from .dialog import event_from_dict

        return event_from_dict(dialog_dict)

    def persist_dialog_state(self, events: List[DialogEvent], dialog_state: DialogState):
        write_items = []
        for event in events:
            write_items.append(
                {
                    "Put": {
                        "TableName": self.events_table_name(),
                        "Item": dynamodb_utils.serialize(event.to_dict()),
                    }
                }
            )
        write_items.append({
            "Put": {
                "TableName": self.state_table_name(),
                "Item": dynamodb_utils.serialize(dialog_state.to_dict())
            }
        )
        self.dynamodb.transact_write_items(TransactItems=write_items)

    def ensure_tables_exist(self):
        # useful for testing but will likely be duplicated elsewhere

        try:
            self.dynamodb.create_table(
                TableName=self.events_table_name(),
                KeySchema=[
                    {"AttributeName": "phone_number", "KeyType": "HASH"},
                    {"AttributeName": "event_id", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "phone_number", "AttributeType": "S"},
                    {"AttributeName": "event_id", "AttributeType": "S"},
                    {"AttributeName": "created_time", "AttributeType": "S"},
                ],
                LocalSecondaryIndexes=[
                    {
                        "IndexName": "by_created_time",
                        "KeySchema": [
                            {"AttributeName": "phone_number", "KeyType": "HASH"},
                            {"AttributeName": "created_time", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            self.dynamodb.create_table(
                TableName=self.state_table_name(),
                KeySchema=[{"AttributeName": "phone_number", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "phone_number", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
        except Exception:
            # table already exists, most likely
            pass
