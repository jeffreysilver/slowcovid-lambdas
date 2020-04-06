from stopcovid.trigger_reminders.trigger_reminders import ReminderTriggerer


def handler(event, context):
    ReminderTriggerer().trigger_reminders()

    return {"statusCode": 200}
