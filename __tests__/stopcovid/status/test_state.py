import unittest
import uuid
from decimal import Decimal


from stopcovid.dialog.models.state import UserProfile


class TestUserProfile(unittest.TestCase):
    def test_json_serialize_user_profile_handles_decimals_and_uuids(self):
        profile = UserProfile(
            validated=True,
            is_demo=True,
            name="Devin Booker",
            language="en",
            account_info={"employer_id": Decimal(91), "a_uuid": uuid.uuid4()},
        )
        expected = {
            "validated": True,
            "is_demo": True,
            "name": "Devin Booker",
            "language": "en",
            "account_info": {"employer_id": 91, "a_uuid": str(profile.account_info["a_uuid"])},
            "opted_out": False,
        }
        self.assertDictContainsSubset(expected, profile.json_serialize())
