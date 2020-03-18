import json
from serverless_sdk import tag_event

def extract_registration_data(form):

    company_name = form.pop(0)["text"]
    owner_first_name = form.pop(0)["text"]
    owner_last_name = form.pop(0)["text"]
    owner_phone = form.pop(0)["phone_number"]
    owner_email = form.pop(0)["email"]

    owner = {
        "first_name": owner_first_name,
        "last_name": owner_last_name,
        "phone": owner_phone,
        "email": owner_email,
    }


    team = []
    while form:
        team.append(
            {
                "first_name": form.pop(0)["text"],
                "last_name":form.pop(0)["text"],
                "unit": form.pop(0)["text"],
                "phone": form.pop(0)["phone_number"],
            }
        )

        # Remove the yes / no question from each team member form. The last team member question doesnt have it
        if len(form):
            form.pop(0)

    return {
        "company_name": company_name,
        "owner": owner,
        "team": team,
    }


def handle_registration(event, context):
    tag_event('registration', 'event', event)

    # form_data = json.loads(event["body"])
    # payload = extract_registration_data(form_data["form_response"]["answers"])

    # hit esl works api

    return {
        "statusCode": 200,
        "body": "hello"
    }