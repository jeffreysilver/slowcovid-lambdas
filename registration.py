import json
import re
from serverless_sdk import tag_event

from clients import eslworks

def format_phone_number(phone):        
    digits = re.sub("\D", "", phone)
    return f"+1{digits}" if len(digits) == 10 else f"+{digits}"

def build_registration_payload(data):

    company_name = data["company-name"]
    owner = {
        "email": data["email"],
    }

    # reconstruct the member ordering from the form
    members = [value for key, value in sorted(data["members"].items(), key=lambda item: int(item[0]))]
    team = [
        {
            "first_name": member["first"],
            "last_name": member["last"],
            "phone": format_phone_number(member["phone"]),
            "unit": member["label"]
        } for member in members if member["first"]
    ]
    
    return {
        "company_name": company_name,
        "owner": owner,
        "team": team,
    }


def handle_registration(event, context):
    tag_event('registration', 'raw_event', event)

    form_data = json.loads(event["body"])
    payload = build_registration_payload(form_data["data"])

    tag_event("registration", "computed_payload", payload)

    eslworks.register(payload)

    return {
        "statusCode": 200,
    }
