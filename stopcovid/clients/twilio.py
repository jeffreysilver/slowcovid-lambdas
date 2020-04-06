from typing import Optional

from twilio.rest import Client
import os


def send_message(to: str, body: str, media_url: Optional[str]):
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    emoji_escaped_body = body.encode("utf-16", "surrogatepass").decode("utf-16")
    return client.messages.create(
        to=to,
        body=emoji_escaped_body,
        media_url=media_url,
        messaging_service_sid=os.environ["TWILIO_MESSAGING_SERVICE_SID"],
    )
