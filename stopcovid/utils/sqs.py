import json


def get_payloads_from_sqs_event(sqs_payload):
    return [json.loads(payload["body"]) for payload in sqs_payload["Records"]]
