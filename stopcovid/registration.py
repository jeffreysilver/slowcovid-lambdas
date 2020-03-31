from collections import OrderedDict
import json
from serverless_sdk import tag_event

from stopcovid.clients import eslworks


def get_labels(data):
    labels = [label.strip() for label in data.get("labels", "").split(",") if label.strip()]

    # remove dups but preserve ordering
    return list(OrderedDict.fromkeys(labels))


def build_registration_payload(data):

    owner = {
        "email": data["email"],
        "first_name": data["first-name"],
        "last_name": data["last-name"],
        "title": data["title"],
    }

    company = {
        "name": data["company-name"],
        "country": data["country"],
        "num_employees": data["employee-count"],
        "zip_code": data["postal-code"],
    }

    labels = get_labels(data)

    return {"company": company, "owner": owner, "labels": labels}


def handle_registration(event, context):
    tag_event("registration", "raw_event", event)

    form_data = json.loads(event["body"])
    payload = build_registration_payload(form_data["data"])

    tag_event("registration", "computed_payload", payload)

    eslworks.register(payload)

    return {"statusCode": 200}
