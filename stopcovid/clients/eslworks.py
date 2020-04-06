import requests
from requests.auth import HTTPBasicAuth
import os

from serverless_sdk import tag_event  # type: ignore

BASE_URL = "https://eslworks-api-staging.herokuapp.com/slowcovid"


def register(payload):
    resp = requests.post(
        f"{BASE_URL}/register",
        auth=HTTPBasicAuth(os.environ.get("AUTH_USERNAME"), os.environ.get("AUTH_PASSWORD")),
        json=payload,
    )
    tag_event("eslworks_register_status", resp.status_code)
    resp.raise_for_status()
    return resp
