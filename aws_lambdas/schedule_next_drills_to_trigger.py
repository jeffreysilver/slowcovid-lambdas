from stopcovid.clients.sqs import publish_drills_to_trigger
from stopcovid.status.drill_progress import DrillProgressRepository

INACTIVITY_THRESHOLD_MINUTES = 720
SCHEDULING_WINDOW_MINUTES = 120


def handler(event, context):
    publish_drills_to_trigger(
        DrillProgressRepository().get_progress_for_users_who_need_drills(
            INACTIVITY_THRESHOLD_MINUTES
        ),
        SCHEDULING_WINDOW_MINUTES,
    )

    return {"statusCode": 200}
