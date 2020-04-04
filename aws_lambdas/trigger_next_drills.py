from stopcovid.status.initiation import trigger_next_drills


def handler(event, context):
    trigger_next_drills()

    return {"statusCode": 200}
