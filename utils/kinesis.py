import ast
from base64 import b64decode


def get_payload_from_kinesis_record(record):
    payload_bytes = b64decode(record["kinesis"]["data"])
    return ast.literal_eval(payload_bytes.decode("UTF-8"))


def get_payloads_from_kinesis_payload(kinesis_payload):
    records = kinesis_payload["Records"]
    return [get_payload_from_kinesis_record(record) for record in records]
