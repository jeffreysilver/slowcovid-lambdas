import ast


def get_payloads_from_sqs_event(sqs_payload):
    return [ast.literal_eval(payload["body"]) for payload in sqs_payload["Records"]]
