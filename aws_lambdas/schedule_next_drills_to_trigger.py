from stopcovid.clients.sqs import publish_drills_to_trigger
from stopcovid.status.drill_progress import DrillProgressRepository
from stopcovid.utils.logging import configure_logging
from stopcovid.utils.verify_deploy_stage import verify_deploy_stage

configure_logging()

INACTIVITY_THRESHOLD_MINUTES = 720
SCHEDULING_WINDOW_MINUTES = 15


def handler(event, context):
    verify_deploy_stage()
    publish_drills_to_trigger(
        DrillProgressRepository().get_progress_for_users_who_need_drills(
            INACTIVITY_THRESHOLD_MINUTES
        ),
        SCHEDULING_WINDOW_MINUTES,
    )

    return {"statusCode": 200}
