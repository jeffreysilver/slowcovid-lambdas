import requests
from requests.auth import HTTPBasicAuth
import os

BASE_URL = "https://eslworks-api-production.herokuapp.com/slowcovid"


def register(payload):
    resp = requests.post(
        f"{BASE_URL}/register",
        auth=HTTPBasicAuth(
            os.environ.get("AUTH_USERNAME"), os.environ.get("AUTH_PASSWORD")
        ),
        json=payload,
    )
    resp.raise_for_status()
    return resp
