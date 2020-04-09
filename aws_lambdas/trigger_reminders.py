from stopcovid.trigger_reminders.trigger_reminders import ReminderTriggerer

from stopcovid.utils.logging import configure_logging
from stopcovid.utils.verify_deploy_stage import verify_deploy_stage

verify_deploy_stage()
configure_logging()


def handler(event, context):
    ReminderTriggerer().trigger_reminders()

    return {"statusCode": 200}
