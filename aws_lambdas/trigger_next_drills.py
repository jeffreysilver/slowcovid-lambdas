from stopcovid.status.initiation import DrillInitiator


def handler(event, context):
    DrillInitiator().trigger_next_drills()

    return {"statusCode": 200}
