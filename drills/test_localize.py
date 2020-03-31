import unittest

from . import localize


class TestLocalize(unittest.TestCase):
    def test_localization(self):
        en = localize.localizations_for("en")
        fr = localize.localizations_for("fr")
        self.assertEqual("Today's drill is:", en["drill_intro_2"])
        self.assertEqual("La formation d'aujourd'hui est: \n", fr["drill_intro_2"])
