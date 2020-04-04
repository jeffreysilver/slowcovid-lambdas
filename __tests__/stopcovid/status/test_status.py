import unittest

from stopcovid.dialog.dialog import UserValidated, DrillStarted
from stopcovid.dialog.registration import CodeValidationPayload
from stopcovid.dialog.types import DialogEventBatch, UserProfile
from stopcovid.drills.drills import get_drill
from stopcovid.status.status import phone_numbers_that_need_first_drill


class TestStatus(unittest.TestCase):
    def setUp(self) -> None:
        self.drill = get_drill("01-basics")

    def test_phone_numbers_that_need_first_drill(self):
        batch1 = DialogEventBatch(
            phone_number="123456789",
            seq="0",
            events=[
                UserValidated(
                    phone_number="123456789",
                    user_profile=UserProfile(True),
                    code_validation_payload=CodeValidationPayload(valid=True),
                ),
                DrillStarted(
                    phone_number="123456789",
                    user_profile=UserProfile(True),
                    drill=self.drill,
                    first_prompt=self.drill.prompts[0],
                ),
            ],
        )
        batch2 = DialogEventBatch(
            phone_number="234567890",
            seq="1",
            events=[
                UserValidated(
                    phone_number="234567890",
                    user_profile=UserProfile(True),
                    code_validation_payload=CodeValidationPayload(valid=True),
                ),
                DrillStarted(
                    phone_number="234567890",
                    user_profile=UserProfile(True),
                    drill=self.drill,
                    first_prompt=self.drill.prompts[0],
                ),
            ],
        )
        batch3 = DialogEventBatch(
            phone_number="987654321",
            seq="1",
            events=[
                DrillStarted(
                    phone_number="987654321",
                    user_profile=UserProfile(True),
                    drill=self.drill,
                    first_prompt=self.drill.prompts[0],
                )
            ],
        )
        self.assertEqual(
            ["123456789", "234567890"],
            phone_numbers_that_need_first_drill([batch1, batch2, batch3]),
        )
