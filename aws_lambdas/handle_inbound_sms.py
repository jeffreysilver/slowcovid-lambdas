from stopcovid.dialog.command_stream.publish import CommandPublisher
from stopcovid.utils.logging import configure_logging

configure_logging()


def handler(event, context):
    CommandPublisher().publish_process_sms_command(event["From"], event["Body"])
    return {"statusCode": 200}
