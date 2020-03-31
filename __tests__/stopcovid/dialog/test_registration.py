import unittest

import requests_mock

from stopcovid.dialog.registration import DefaultRegistrationValidator


class TestRegistration(unittest.TestCase):
    def setUp(self) -> None:
        self.url = "https://foo"
        self.key = "access-key"

    def test_invalid_code(self):
        with requests_mock.Mocker() as m:
            m.post(self.url, json={"valid": False})
            payload = DefaultRegistrationValidator().validate_code(
                "foo", url=self.url, key=self.key
            )

        self.assertFalse(payload.valid)

    def test_demo_code(self):
        with requests_mock.Mocker() as m:
            m.post(self.url, json={"valid": True, "is_demo": True})
            payload = DefaultRegistrationValidator().validate_code(
                "foo", url=self.url, key=self.key
            )

        self.assertTrue(payload.valid)
        self.assertTrue(payload.is_demo)

    def test_valid_non_demo_code(self):
        with requests_mock.Mocker() as m:
            m.post(
                self.url,
                json={
                    "valid": True,
                    "is_demo": False,
                    "account_info": {"employer_id": 165, "unit_id": 429},
                },
            )
            payload = DefaultRegistrationValidator().validate_code(
                "foo", url=self.url, key=self.key
            )

        self.assertTrue(payload.valid)
        self.assertFalse(payload.is_demo)
        self.assertEqual({"employer_id": 165, "unit_id": 429}, payload.account_info)
