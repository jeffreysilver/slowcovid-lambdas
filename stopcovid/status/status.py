from stopcovid.dialog.types import DialogEvent
from .drill_instances import DrillInstanceRepository
from .users import UserRepository


def handle_dialog_event(event: DialogEvent):
    user_repo = UserRepository()
    user_id = user_repo.create_or_update_user(event.phone_number, event.user_profile)

    drill_instance_repo = DrillInstanceRepository()
    drill_instance_repo.update_drill_instances(user_id, event)
