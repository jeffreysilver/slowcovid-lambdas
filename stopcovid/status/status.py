import itertools
from typing import List

from stopcovid.dialog.types import DialogEventBatch
from .drill_instances import DrillInstanceRepository
from .initiation import trigger_first_drill
from .users import UserRepository
from ..dialog.dialog import UserValidated


def handle_dialog_event_batches(batches: List[DialogEventBatch]):
    user_repo = UserRepository()

    # trigger initiation before updating status. The status updates could be slow because of
    # aurora cold start time.
    trigger_first_drill(phone_numbers_that_need_first_drill(batches))

    for batch in batches:
        user_id = user_repo.update_user(batch)

        drill_instance_repo = DrillInstanceRepository()
        drill_instance_repo.update_drill_instances(user_id, batch)


def phone_numbers_that_need_first_drill(batches: List[DialogEventBatch]):
    events = itertools.chain.from_iterable(batch.events for batch in batches)
    return [event.phone_number for event in events if isinstance(event, UserValidated)]
