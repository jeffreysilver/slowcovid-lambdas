import unittest

from stopcovid.drills import drills


class TestGetDrill(unittest.TestCase):
    def test_get_drill(self):
        drill = drills.get_drill("01-basics")
        self.assertEqual("01. COVID19: Basics", drill.name)
