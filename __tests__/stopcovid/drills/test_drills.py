import json
import os
import unittest
from unittest.mock import patch

from jinja2 import TemplateSyntaxError

from stopcovid.drills import drills

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

from stopcovid.drills.localize import localize


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
            drill = drills.get_drill(slug)
            for prompt in drill.prompts:
                try:
                    for message in prompt.messages:
                        localize(message.text, "en", name="foo", company="WeWork")
                    if prompt.correct_response is not None:
                        localize(prompt.correct_response, "en")
                except TemplateSyntaxError:
                    self.fail(f"error localizing drill {slug} and prompt {prompt.slug}")


class TestPrompt(unittest.TestCase):
    def test_should_advance_ignore(self):
        prompt = drills.Prompt(slug="test-prompt", messages=[drills.PromptMessage("{{msg1}}")])
        self.assertTrue(prompt.should_advance_with_answer("any answer", "en"))

    def test_should_advance_store(self):
        prompt = drills.Prompt(
            slug="test-prompt",
            messages=[drills.PromptMessage("{{msg1}}")],
            response_user_profile_key="self_rating_7",
        )
        self.assertTrue(prompt.should_advance_with_answer("any answer", "en"))

    def test_should_advance_graded(self):
        prompt = drills.Prompt(
            slug="test-prompt",
            messages=[drills.PromptMessage("{{msg1}}")],
            correct_response="{{resp1}}",
        )
        with patch("stopcovid.drills.drills.localize") as localize_mock:
            localize_mock.return_value = "my response"
            self.assertFalse(
                prompt.should_advance_with_answer("something completely different", "en")
            )
            self.assertTrue(prompt.should_advance_with_answer("my response", "en"))
