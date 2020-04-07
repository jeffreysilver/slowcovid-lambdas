import boto3
from time import sleep
import json
import os

from twilio.rest import Client


SYSTEM_TEST_PHONE_NUMBER = "+12152733053"
STOPCOVID_DEV_PHONE_NUMBER = "+14707190649"


class SystemTest:
    def __init__(self):
        sqs = boto3.resource("sqs")
        self.queue = sqs.get_queue_by_name(QueueName="system-test-dev")
        self.twilio_client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        self.drill_complete = False

    def respond(self, body):
        print("Responding:", body)
        self.twilio_client.messages.create(
            to=STOPCOVID_DEV_PHONE_NUMBER, from_=SYSTEM_TEST_PHONE_NUMBER, body=body,
        )

    def kick_off_drill(self):
        self.respond("stopcovid")

    def _handle_response(self, text):
        lowered_text = text.lower()

        if "choose your language" in lowered_text:
            self.respond("en")

        if "text me the word go" in lowered_text:
            self.respond("go")

        if "on a scale of 1-10" in lowered_text:
            self.respond("7")

        if "what's your full name" in lowered_text:
            self.respond("mr robot")

        if "PRACTICE" in text:
            self.respond("a")

        if "try again" in lowered_text:
            self.respond("b")

        if "drill is complete" in lowered_text:
            self.drill_complete = True

    def proceed_through_drill(self):
        idle_count = 0
        while not self.drill_complete:
            if idle_count > 5:
                raise RuntimeError("System is not responding in time.")

            print(".")
            messages = self.queue.receive_messages(WaitTimeSeconds=1)
            if messages:
                idle_count = 0
                for message in messages:
                    sms = json.loads(message.body)
                    text = sms["Body"]
                    print("Received:", text)
                    self._handle_response(text)
                    message.delete()
            else:
                idle_count += 1

            sleep(1)

    def execute(self):
        self.kick_off_drill()
        self.proceed_through_drill()
        print("System test complete")


if __name__ == "__main__":
    SystemTest().execute()
