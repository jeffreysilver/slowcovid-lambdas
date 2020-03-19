import requests
import base64
from requests.auth import HTTPBasicAuth
import os

from serverless_sdk import tag_event


def register(payload):
    resp = requests.post("https://eslworks-api-staging.herokuapp.com/slowcovid/register", auth=HTTPBasicAuth(os.environ.get("AUTH_USERNAME"), os.environ.get("AUTH_PASSWORD")), json=payload)
    tag_event("eslworks_register_status", resp.status_code)
    resp.raise_for_status()
    return resp
    