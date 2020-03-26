from serverless_sdk import tag_event
import json
import ast
from base64 import b64decode
from clients import rds
import os

def store_inbound_sms(event, context):
    tag_event('inbound_sms', 'raw_event', event)
    
    for record in event["Records"]:
        kinesis_payload = record["kinesis"]
        base64_data = kinesis_payload["data"]
        dict_bytes = b64decode(base64_data)
        sms = ast.literal_eval(dict_bytes.decode("UTF-8"))
        tag_event("inbound_sms", "message_payload", sms)
        rds_response = rds.insert_message(sms["MessageSid"], sms["Body"], sms["From"], sms["To"], kinesis_payload["approximateArrivalTimestamp"], kinesis_payload["sequenceNumber"])
        tag_event("inbound_sms", "rds_response", rds_response)

    return {
        "statusCode": 200,
    }