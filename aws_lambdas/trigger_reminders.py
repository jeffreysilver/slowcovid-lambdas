from stopcovid.trigger_reminders.trigger_reminders import ReminderTriggerer

from stopcovid.utils.logging import configure_logging

configure_logging()


def handler(event, context):
    ReminderTriggerer().trigger_reminders()

    return {"statusCode": 200}
