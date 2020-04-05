from typing import List

from stopcovid.dialog.types import DialogEventBatch
from .drill_instances import DrillInstanceRepository
from .initiation import DrillInitiator
from .users import UserRepository
from ..dialog.dialog import UserValidated, NextDrillRequested


def handle_dialog_event_batches(batches: List[DialogEventBatch]):
    # trigger initiation before updating status. The status updates could be slow because of
    # aurora cold start time.
    initiator = DrillInitiator()
    for batch in batches:
        if initiates_first_drill(batch):
            initiator.trigger_first_drill(batch.phone_number, str(batch.batch_id))

    user_repo = UserRepository()
    drill_instance_repo = DrillInstanceRepository()
    for batch in batches:
        user_id = user_repo.update_user(batch)
        if initiates_subsequent_drill(batch):
            initiator.trigger_next_drill_for_user(user_id, batch.phone_number, str(batch.batch_id))
        drill_instance_repo.update_drill_instances(user_id, batch)


def initiates_first_drill(batch: DialogEventBatch):
    return any(event for event in batch.events if isinstance(event, UserValidated))


def initiates_subsequent_drill(batch: DialogEventBatch):
    return any(event for event in batch.events if isinstance(event, NextDrillRequested))
