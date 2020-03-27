from twilio.rest import Client
import os


def send_message(to, body):
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    emoji_escaped_body = body.encode('utf-16','surrogatepass').decode('utf-16')
    res = client.messages.create(
        to=to,
        body=emoji_escaped_body,
        messaging_service_sid=os.environ["TWILIO_MESSAGING_SERVICE_SID"],
    )
    return {
        "status": res.status,
        "uri": res.uri,
        "to": res.to,
        "body": res.body,
        "error_code": res.error_code,
        "error_message": res.error_message,
    }