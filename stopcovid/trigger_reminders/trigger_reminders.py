import os

from stopcovid.drill_progress.drill_progress import DrillProgressRepository

from . import persistence
from ..dialog.command_stream.publish import CommandPublisher

REMINDER_TRIGGER_FLOOR_MINUTES = 60 * 4
REMINDER_TRIGGER_CEIL_MINUTES = 60 * 24


class ReminderTriggerer:
    def __init__(self, **kwargs):
        self.stage = os.environ.get("STAGE")
        self.reminder_trigger_repo = self._get_reminder_trigger_repo()
        self.drill_progress_repo = self._get_drill_progress_repo()
        self.command_publisher = CommandPublisher()

    def _get_reminder_trigger_repo(self) -> persistence.ReminderTriggerRepository:
        return persistence.ReminderTriggerRepository()

    def _get_drill_progress_repo(self):
        return DrillProgressRepository()

    def trigger_reminders(self):
        drill_instances = self.drill_progress_repo.get_incomplete_drills(
            inactive_for_minutes_floor=REMINDER_TRIGGER_FLOOR_MINUTES,
            inactive_for_minutes_ceil=REMINDER_TRIGGER_CEIL_MINUTES,
        )
        drill_instances_to_remind_on = [
            drill_instance
            for drill_instance in drill_instances
            if not self.reminder_trigger_repo.reminder_trigger_exists(
                drill_instance_id=drill_instance.drill_instance_id,
                prompt_slug=drill_instance.current_prompt_slug,
            )
        ]
        if not drill_instances_to_remind_on:
            return

        # The dialog agent wont send a reminder for the same drill/prompt combo twice
        # publishing to the stream twice should be avoided, but isn't a big deal.
        self.command_publisher.publish_trigger_reminder_commands(drill_instances_to_remind_on)
        self.reminder_trigger_repo.save_reminder_triggers_for_drills(drill_instances_to_remind_on)
