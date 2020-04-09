import unittest
from decimal import Decimal


from stopcovid.dialog.models.state import UserProfile


class TestUserProfile(unittest.TestCase):
    def test_json_serialize_user_profile_handles_decimals_and_uuids(self):
        profile = UserProfile(
            validated=True,
            is_demo=True,
            name="Devin Booker",
            language="en",
            account_info={"employer_id": Decimal(91), "unit_id": Decimal(19)},
        )
        expected = {
            "validated": True,
            "is_demo": True,
            "name": "Devin Booker",
            "language": "en",
            "account_info": {"employer_id": 91, "unit_id": 19},
            "opted_out": False,
        }

        print(profile.to_dict())
        self.assertDictContainsSubset(expected, profile.to_dict())
        # self.assertTrue(set(expected.items()).issubset( set(profile.to_dict().items()) ))
        # And changes are immutabe
        assert expected.items() <= profile.to_dict().items()
        self.assertEqual(profile.account_info["employer_id"], Decimal(91))
