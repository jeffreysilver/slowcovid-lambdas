from abc import ABC, abstractmethod
from typing import List

from .types import DialogState, DialogEvent


class DialogRepository(ABC):
    @abstractmethod
    def fetch_dialog_state(self, phone_number: str) -> DialogState:
        pass

    @abstractmethod
    def persist_dialog_state(self, events: List[DialogEvent], dialog_state: DialogState):
        pass


class DynamoDBDialogRepository(DialogRepository):
    def fetch_dialog_state(self, phone_number: str) -> DialogState:
        pass

    def persist_dialog_state(self, events: List[DialogEvent], dialog_state: DialogState):
        pass

    def create_tables(self):
        pass
