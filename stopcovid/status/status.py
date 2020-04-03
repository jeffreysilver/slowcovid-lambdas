from stopcovid.dialog.types import DialogEvent
from .drill_instances import DrillInstanceRepository
from .users import UserRepository


def handle_dialog_event(event: DialogEvent):
    user_repo = UserRepository()

    # not worrying a lot about transactions here. All of these operations are idempotent
    # and we're operating in a context in which we get only one event per phone number at a time.

    user_id = user_repo.create_or_update_user(event.phone_number, event.user_profile)
    user_repo.update_user_progress(user_id, event)

    drill_instance_repo = DrillInstanceRepository()
    drill_instance_repo.update_drill_instances(user_id, event)
