import boto3
import os
import json


KINESIS = boto3.client("kinesis")


def publish_log_outbound_sms(twilio_responses):

    stage = os.environ.get("STAGE")

    records = [
        {
            "Data": json.dumps(
                {
                    "type": "OUTBOUND_SMS",
                    "payload": {
                        "MessageSid": response.sid,
                        "To": response.to,
                        "Body": response.body,
                        "MessageStatus": response.status,
                    },
                }
            ),
            "PartitionKey": response.to,
        }
        for response in twilio_responses
    ]

    return KINESIS.put_records(Records=records, StreamName=f"message-log-{stage}",)
