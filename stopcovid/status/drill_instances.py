import datetime
import uuid
from dataclasses import dataclass
from typing import Union, Optional

from stopcovid.dialog.dialog import (
    AdvancedToNextPrompt,
    CompletedPrompt,
    FailedPrompt,
    DrillCompleted,
    DrillStarted,
    UserValidated,
)
from stopcovid.dialog.types import DialogEvent


@dataclass
class DrillInstance:
    drill_instance_id: uuid.UUID
    user_id: uuid.UUID
    drill_slug: str
    current_prompt_slug: str
    current_prompt_start_time: datetime.datetime
    current_prompt_last_response_time: Optional[datetime.datetime] = None
    is_complete: bool = False
    is_invalid: bool = False


def update_drill_instances(event: DialogEvent):
    if isinstance(event, UserValidated):
        invalidate_prior_drills(user_id)
    if isinstance(event, DrillStarted):
        record_new_drill_instance(user_id, event)
    if isinstance(event, DrillCompleted):
        mark_drill_instance_complete(user_id, event)
    if isinstance(event, CompletedPrompt):
        update_current_prompt_response_time(user_id, event)
    if isinstance(event, FailedPrompt):
        update_current_prompt_response_time(user_id, event)
    if isinstance(event, AdvancedToNextPrompt):
        update_current_prompt(user_id, event)


def invalidate_prior_drills(user_id: uuid.UUID):
    pass


def record_new_drill_instance(user_id: uuid.UUID, event: DrillStarted):
    pass


def mark_drill_instance_complete(user_id: uuid.UUID, event: DrillCompleted):
    pass


def update_current_prompt_response_time(
    user_id: uuid.UUID, event: Union[FailedPrompt, CompletedPrompt]
):
    pass


def update_current_prompt(user_id: uuid.UUID, event: AdvancedToNextPrompt):
    pass


def ensure_tables_exist():
    pass
