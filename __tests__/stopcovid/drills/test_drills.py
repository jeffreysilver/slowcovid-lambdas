import json
import os
import unittest

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
