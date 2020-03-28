# -*- coding: utf-8 -*-
import sys
import uuid
from time import sleep
from typing import List

from dialog import (
    DialogEvent, DialogState, DialogRepository, DialogStateSchema, DialogEventType,
    process_command, StartDrill,
    ProcessSMSMessage
)
from drills import Drill, Prompt

TRY_AGAIN = "Sorry, not correct.\n\n*Try again one more time!*"
PHONE_NUMBER = "123456789"
DRILL = Drill(
    drill_id=uuid.uuid4(),
    prompts=[
        Prompt(
            slug="language",
            messages=[
                "Welcome! Choose your language:\nen - English\nes - Español\n"
                "fr - Français\npt - Português\nzh - Chinese 中文"
            ],
            response_user_profile_key="language"
        ),
        Prompt(
            slug="begin-drill",
            messages=[
                "Thank you for dedicating your time to StopCovid training. "
                "By completing one training everyday, you are helping prevent "
                "the spread of Coronavirus.",
                "Today's drill is: COVID-19 Basics. Text me the word GO "
                "when you're ready to start."
            ]
        ),
        Prompt(
            slug="get-name",
            messages=[
                "What's your full name?\n(First and Last)"
            ],
            response_user_profile_key="name"
        ),
        Prompt(
            slug="rate-knowledge",
            messages=[
                "Ok! Here we go! Let’s learn a little bit about you first.",
                "On a scale of 1-10, how would you rate your current knowledge of "
                "today's topic: COVID-19 Basics.\n\n(1 = I don't know anything, 10 = I'm "
                "great and I teach others)",
                "(Your answer will be kept private.)"
            ],
            response_user_profile_key="self_rating"
        ),
        Prompt(
            slug="q-bacteria",
            messages=["PRACTICE 1: True or false?\n\nCOVID-19 is a bacteria.\n\n"
                      "a) true\nb) false"],
            correct_option="b) false",
            correct_option_code="b",
        ),
        Prompt(
            slug="q-flu",
            messages=["FACT:  COVID-19 is not a bacteria. It is a virus disease. If "
                      "you hear someone say “coronavirus” or “novel coronavirus,” they are"
                      " talking about the same thing.",
                      "PRACTICE 2: Fill in the blank by choosing the best answer.\n\n"
                      "COVID-19 is [---] the flu.\n\na) as contagious as\nb) less "
                      "contagious than\nc) more contagious than"],
            correct_option="c) more contagious than",
            correct_option_code="c"
        ),
        Prompt(
            slug="q-spread",
            messages=["FACT: COVID-19 is more contagious and deadly than the flu. It is "
                      "important that we all work together to control its spread and save "
                      "lives.",
                      "PRACTICE 3: Answer the question. \n\nHow is COVID-19 spread from "
                      "person\nto person?\n\na) Contact with an infected person\nb) An "
                      "infected person coughs or sneezes\nc) Touching a surface with "
                      "COVID-19 on it, then touching your face\nd) All of the above"],
            correct_option="d) All of the above",
            correct_option_code="d",
        ),
        Prompt(
            slug="q-symptoms",
            messages=["FACT: It's possible for COVID-19 to be spread by people who don’t "
                      "show symptoms. Keep your distance with other people + practice good "
                      "hygiene all the time.",
                      "PRACTICE 4: Answer the question.\n\nWhat are the most common symptoms "
                      "of COVID-19?\n\na) Stomachache, nausea, diarrhea\nb) Fever, cough, "
                      "shortness of breath\nc) Itchy rash\nd) Blurred vision"],
            correct_option="b) Fever, cough, shortness of breath",
            correct_option_code="b"
        ),
        Prompt(
            slug="q-care",
            messages=["Almost done!",
                      "FACT: If you or someone near you has difficulty breathing, chest "
                      "pain, confusion, or blue lips, get medical attention immediately.",
                      "PRACTICE 5: If you think you may have symptoms of COVID-19, you should"
                      " [---]. \n\na) stay home, except to get medical care\nb) don't take "
                      "public transportation\nc) call your doctor before you visit \nd) all "
                      "of the above"],
            correct_option="d) all of the above",
            correct_option_code="d"
        ),
        Prompt(
            slug="conclusion",
            messages=["FACT: If you are experiencing only mild symptoms, self isolate to"
                      "control the spread of COVID-19.",
                      "Congrats! Your training drill for today is complete.\n\nYou will get "
                      "your next drill tomorrow afternoon!"]
        )
    ],
)


def fake_sms(phone_number: str, messages: List[str], with_initial_pause=False):
    first = True
    for message in messages:
        if with_initial_pause or not first:
            sleep(3)
        first = False
        print(f"  -> {phone_number}: {message}")
        first = False


class InMemoryRepository(DialogRepository):
    def __init__(self):
        self.repo = {}

    def fetch_dialog_state(self, phone_number: str) -> DialogState:
        if phone_number in self.repo:
            return DialogStateSchema().loads(self.repo[phone_number])
        else:
            return DialogState(phone_number=phone_number)

    def persist_dialog_state(self, events: List[DialogEvent], dialog_state: DialogState):
        self.repo[dialog_state.phone_number] = DialogStateSchema().dumps(dialog_state)

        should_start_drill = False
        for event in events:
            if event.event_type == DialogEventType.ADVANCED_TO_NEXT_PROMPT:
                fake_sms(event.phone_number, event.prompt.messages, with_initial_pause=True)
            elif event.event_type == DialogEventType.FAILED_PROMPT:
                if not event.abandoned:
                    fake_sms(event.phone_number, [TRY_AGAIN])
                else:
                    fake_sms(event.phone_number, [
                        f"The correct answer is *{event.prompt.correct_option}*.\n\n"
                        f"Lets move to the next one."
                    ])
            elif event.event_type == DialogEventType.COMPLETED_PROMPT:
                if event.prompt.is_graded():
                    fake_sms(event.phone_number, ["Correct!"])
                elif event.prompt.stores_answer():
                    fake_sms(event.phone_number, ["Thanks!"])
            elif event.event_type == DialogEventType.USER_CREATED:
                should_start_drill = True
            elif event.event_type == DialogEventType.USER_CREATION_FAILED:
                print("(try DRILL0)")
            elif event.event_type == DialogEventType.DRILL_STARTED:
                fake_sms(event.phone_number, event.prompt.messages)
            elif event.event_type == DialogEventType.DRILL_COMPLETED:
                print("(The drill is complete. Type crtl-D to exit.)")
        if should_start_drill:
            process_command(StartDrill(PHONE_NUMBER, DRILL), repo=self)


def main():
    repo = InMemoryRepository()
    try:
        while True:
            message = input("> ")
            process_command(ProcessSMSMessage(PHONE_NUMBER, message), repo=repo)
    except EOFError:
        pass
    dialog_state = repo.fetch_dialog_state(PHONE_NUMBER)
    print(f"{dialog_state.user_profile}")


if __name__ == "__main__":
    main()
