import unittest

from . import localize


class TestLocalize(unittest.TestCase):
    def test_localization(self):
        self.assertEqual("Today's drill is:", localize.localize("{{drill_intro_2}}", "en"))
        self.assertEqual("La formation d'aujourd'hui est: \n",
                         localize.localize("{{drill_intro_2}}", "fr"))
        self.assertEqual("Today's drill is:", localize.localize("{{drill_intro_2}}", "xx"))
