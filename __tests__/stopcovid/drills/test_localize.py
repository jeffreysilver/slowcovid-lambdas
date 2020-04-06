import unittest

from stopcovid.drills import localize


class TestLocalize(unittest.TestCase):
    def test_localization(self):
        self.assertEqual("Your next drill is:", localize.localize("{{drill_intro_2}}", "en"))
        self.assertEqual(
            "Sa prochaine formation est:\n", localize.localize("{{drill_intro_2}}", "fr")
        )
        self.assertEqual("Your next drill is:", localize.localize("{{drill_intro_2}}", "xx"))
