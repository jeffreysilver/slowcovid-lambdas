import unittest

from dialog.dialog import CompletedPrompt, AdvancedToNextPrompt
from dialog.persistence import DynamoDBDialogRepository
from dialog.types import DialogState, UserProfile
from drills.drills import Prompt


class TestPersistence(unittest.TestCase):
    """
    requires local dynamoDB to be running: docker-compose up in the dynamodb_local directory
    """

    def setUp(self):
        self.repo = DynamoDBDialogRepository(
            region_name="us-west-2",
            endpoint_url="http://localhost:9000",
        )
        self.repo.ensure_tables_exist()
        self.phone_number = "123456789"

    def test_save_and_fetch(self):
        dialog_state = self.repo.fetch_dialog_state(self.phone_number)
        self.assertEqual(self.phone_number, dialog_state.phone_number)

        event1 = CompletedPrompt(
            phone_number=self.phone_number,
            prompt=Prompt(
                slug="one",
                messages=["one", "two"]
            ),
            response="hi"
        )
        event2 = AdvancedToNextPrompt(
            phone_number=self.phone_number,
            prompt=Prompt(
                slug="two",
                messages=["three", "four"]
            )
        )
        dialog_state = DialogState(
            self.phone_number,
            user_profile=UserProfile(validated=True, language="de")
        )
        self.repo.persist_dialog_state([event1, event2], dialog_state)
        dialog_state2 = self.repo.fetch_dialog_state(self.phone_number)
        self.assertEqual(dialog_state.phone_number, dialog_state2.phone_number)
        self.assertEqual(dialog_state.user_profile.validated, dialog_state2.user_profile.validated)
        self.assertEqual(dialog_state.user_profile.language, dialog_state2.user_profile.language)

        event1_retrieved = self.repo.fetch_dialog_event(self.phone_number, event1.event_id)
        self.assertEqual(event1.response, event1_retrieved.response)

        event2_retrieved = self.repo.fetch_dialog_event(self.phone_number, event2.event_id)
        self.assertEqual(event2.prompt.slug, event2_retrieved.prompt.slug)
