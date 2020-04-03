from stopcovid.dialog.types import DialogEventBatch
from .drill_instances import DrillInstanceRepository
from .users import UserRepository


def handle_dialog_event_batch(batch: DialogEventBatch):
    user_repo = UserRepository()

    # not worrying a lot about transactions here. All of these operations are idempotent
    # and we're operating in a context in which we get only one event per phone number at a time.

    user_id = user_repo.update_user(batch)

    drill_instance_repo = DrillInstanceRepository()
    drill_instance_repo.update_drill_instances(user_id, batch)
