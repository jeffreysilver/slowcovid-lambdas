import unittest

from stopcovid.dialog.types import UserProfile
from stopcovid.status.db import get_test_sqlalchemy_engine
from stopcovid.status.users import (
    drop_and_recreate_tables_testing_only,
    create_or_update_user,
    get_user,
)


class TestUsers(unittest.TestCase):
    def setUp(self):
        self.engine_factory = get_test_sqlalchemy_engine
        drop_and_recreate_tables_testing_only(self.engine_factory)

    def test_create_or_update_user(self):
        profile = UserProfile(True, account_info={"foo": "bar"})
        user_id = create_or_update_user("123456789", profile, engine_factory=self.engine_factory)
        user = get_user(user_id, engine_factory=self.engine_factory)
        self.assertEqual(user_id, user.user_id)
        self.assertEqual({"foo": "bar"}, user.account_info)
        self.assertIsNone(user.last_interacted_time)

        profile.account_info["one"] = "two"
        create_or_update_user("123456789", profile, engine_factory=self.engine_factory)
        user = get_user(user_id, engine_factory=self.engine_factory)
        self.assertEqual({"foo": "bar", "one": "two"}, user.account_info)
