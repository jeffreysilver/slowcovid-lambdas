import unittest

from stopcovid.dialog.types import UserProfile
from stopcovid.status.db import get_test_sqlalchemy_engine
from stopcovid.status.users import UserRepository


class TestUsers(unittest.TestCase):
    def setUp(self):
        self.repo = UserRepository(get_test_sqlalchemy_engine)
        self.repo.drop_and_recreate_tables_testing_only()

    def test_create_or_update_user(self):
        profile = UserProfile(True, account_info={"foo": "bar"})
        user_id = self.repo.create_or_update_user("123456789", profile)
        user = self.repo.get_user(user_id)
        self.assertEqual(user_id, user.user_id)
        self.assertEqual({"foo": "bar"}, user.account_info)
        self.assertIsNone(user.last_interacted_time)

        profile.account_info["one"] = "two"
        self.repo.create_or_update_user("123456789", profile)
        user = self.repo.get_user(user_id)
        self.assertEqual({"foo": "bar", "one": "two"}, user.account_info)
