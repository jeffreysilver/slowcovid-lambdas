from stopcovid.utils.kinesis import get_payloads_from_kinesis_event
from stopcovid.message_log.message_log import log_messages
from stopcovid.message_log.types import LogMessageCommandSchema


def handle(event, context):
    raw_commands = get_payloads_from_kinesis_event(event)
    commands = [
        LogMessageCommandSchema().load(
            {"command_type": command["type"], "payload": command["payload"]}
        )
        for command in raw_commands
    ]
    log_messages(commands)
    return {"statusCode": 200}
