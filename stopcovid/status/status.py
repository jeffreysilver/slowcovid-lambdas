from stopcovid.dialog.types import DialogEvent
from .drill_instances import update_drill_instances
from .users import create_or_update_user, update_user_progress


def handle_dialog_event(event: DialogEvent):
    create_or_update_user(event.phone_number, event.user_profile)
    update_drill_instances(event)
    update_user_progress(event)
