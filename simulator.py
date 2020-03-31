# -*- coding: utf-8 -*-
import sys
from time import sleep
from typing import List

from stopcovid.dialog.dialog import DialogRepository, process_command, StartDrill, ProcessSMSMessage
from stopcovid.dialog.registration import RegistrationValidator, CodeValidationPayload
from stopcovid.dialog.types import (
    DialogStateSchema,
    DialogEventType,
    DialogEvent,
    DialogState,
    UserProfile,
)
from stopcovid.drills.drills import get_drill
from stopcovid.drills.localize import localize

SEQ = 1
TRY_AGAIN = "{{incorrect_answer}}"
PHONE_NUMBER = "123456789"
DRILLS = {
    "drill1": get_drill("01-basics"),
    "drill2": get_drill("02-prevention"),
    "drill3": get_drill("03-hand-washing-how"),
    "drill4": get_drill("04-hand-sanitizer"),
    "drill5": get_drill("05-disinfect-phone"),
    "drill6": get_drill("06-hand-washing-when"),
    "drill7": get_drill("07-sanitizing-surfaces"),
}


def fake_sms(
    phone_number: str,
    user_profile: UserProfile,
    messages: List[str],
    with_initial_pause=False,
    **kwargs,
):
    first = True
    for message in messages:
        if with_initial_pause or not first:
            sleep(1)
        first = False
        print(f"  -> {phone_number}: {localize(message, user_profile.language, **kwargs)}")
        first = False


class InMemoryRepository(DialogRepository):
    def __init__(self, lang):
        self.repo = {}
        self.lang = lang

    def fetch_dialog_state(self, phone_number: str) -> DialogState:
        if phone_number in self.repo:
            state = DialogStateSchema().loads(self.repo[phone_number])
            state.user_profile.language = self.lang
            return state
        else:
            return DialogState(phone_number=phone_number, seq="0")

    def persist_dialog_state(self, events: List[DialogEvent], dialog_state: DialogState):
        self.repo[dialog_state.phone_number] = DialogStateSchema().dumps(dialog_state)

        should_start_drill = False
        for event in events:
            if event.event_type == DialogEventType.ADVANCED_TO_NEXT_PROMPT:
                fake_sms(
                    event.phone_number,
                    dialog_state.user_profile,
                    event.prompt.messages,
                    with_initial_pause=True,
                )
            elif event.event_type == DialogEventType.FAILED_PROMPT:
                if not event.abandoned:
                    fake_sms(event.phone_number, dialog_state.user_profile, [TRY_AGAIN])
                else:
                    fake_sms(
                        event.phone_number,
                        dialog_state.user_profile,
                        ["{{corrected_answer}}"],
                        correct_answer=localize(
                            event.prompt.correct_response, dialog_state.user_profile.language
                        ),
                    )
            elif event.event_type == DialogEventType.COMPLETED_PROMPT:
                if event.prompt.is_graded():
                    fake_sms(event.phone_number, dialog_state.user_profile, ["{{right}}"])
            elif event.event_type == DialogEventType.USER_VALIDATED:
                should_start_drill = True
            elif event.event_type == DialogEventType.USER_VALIDATION_FAILED:
                print("(try DRILL1, DRILL2, DRILL3, DRILL4, DRILL5, DRILL6, DRILL7)")
            elif event.event_type == DialogEventType.DRILL_STARTED:
                fake_sms(event.phone_number, dialog_state.user_profile, event.first_prompt.messages)
            elif event.event_type == DialogEventType.DRILL_COMPLETED:
                print("(The drill is complete. Type crtl-D to exit.)")
        if should_start_drill:
            global SEQ
            SEQ += 1
            process_command(
                StartDrill(PHONE_NUMBER, DRILLS[dialog_state.user_profile.account_info["code"]]),
                str(SEQ),
                repo=self,
            )


class FakeRegistrationValidator(RegistrationValidator):
    def validate_code(self, code) -> CodeValidationPayload:
        if code in ["drill1", "drill2", "drill3", "drill4", "drill5", "drill6", "drill7"]:
            return CodeValidationPayload(valid=True, account_info={"code": code})
        return CodeValidationPayload(valid=False)


def main():
    global SEQ
    if len(sys.argv) > 1:
        lang = sys.argv[1]
    else:
        lang = "en"
    repo = InMemoryRepository(lang)
    validator = FakeRegistrationValidator()
    try:
        while True:
            message = input("> ")
            SEQ += 1
            process_command(
                ProcessSMSMessage(PHONE_NUMBER, message, registration_validator=validator),
                str(SEQ),
                repo=repo,
            )
    except EOFError:
        pass
    dialog_state = repo.fetch_dialog_state(PHONE_NUMBER)
    print(f"{dialog_state.user_profile}")


if __name__ == "__main__":
    main()
