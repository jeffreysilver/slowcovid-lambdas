import json
import os
import unittest
from unittest.mock import patch

from stopcovid.drills import drills

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


class TestGetDrill(unittest.TestCase):
    def test_get_drill(self):
        drill = drills.get_drill("01-basics")
        self.assertEqual("01. COVID19: Basics", drill.name)


class TestDrillFileIntegrity(unittest.TestCase):
    def test_drill_file_integrity(self):
        filename = os.path.join(__location__, "../../../stopcovid/drills/drill_content/drills.json")
        with open(filename) as r:
            contents = r.read()
            drills_dict = json.loads(contents)
            for slug, drill_dict in drills_dict.items():
                self.assertEqual(slug, drill_dict["slug"])
                drills.get_drill(slug)  # make sure it doesn't blow up


class TestPrompt(unittest.TestCase):
    def test_should_advance_ignore(self):
        prompt = drills.Prompt(slug="test-prompt", messages=["{{msg1}}"])
        self.assertTrue(prompt.should_advance_with_answer("any answer", "en"))

    def test_should_advance_store(self):
        prompt = drills.Prompt(
            slug="test-prompt", messages=["{{msg1}}"], response_user_profile_key="self_rating_7"
        )
        self.assertTrue(prompt.should_advance_with_answer("any answer", "en"))

    def test_should_advance_graded(self):
        prompt = drills.Prompt(
            slug="test-prompt", messages=["{{msg1}}"], correct_response="{{resp1}}"
        )
        with patch("stopcovid.drills.drills.localize") as localize_mock:
            localize_mock.return_value = "my response"
            self.assertFalse(
                prompt.should_advance_with_answer("something completely different", "en")
            )
            self.assertTrue(prompt.should_advance_with_answer("my response", "en"))
