import datetime
import logging
import uuid
from dataclasses import dataclass
from typing import Union, Optional, List

from sqlalchemy import MetaData, Table, Column, String, DateTime, Boolean, select, func, insert
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import DatabaseError, IntegrityError

from stopcovid.dialog.dialog import (
    AdvancedToNextPrompt,
    CompletedPrompt,
    FailedPrompt,
    DrillCompleted,
    DrillStarted,
    UserValidated,
    UserValidationFailed,
    ReminderTriggered,
)
from stopcovid.dialog.types import DialogEvent
from . import db

metadata = MetaData()
drill_instances = Table(
    "drill_instances",
    metadata,
    Column("drill_instance_id", UUID, primary_key=True),
    Column("user_id", UUID, nullable=False),
    Column("phone_number", String, nullable=False),
    Column("drill_slug", String, nullable=False),
    Column("current_prompt_slug", String, nullable=True),
    Column("current_prompt_start_time", DateTime(timezone=True), nullable=True),
    Column("current_prompt_last_response_time", DateTime(timezone=True), nullable=True),
    Column("completion_time", DateTime(timezone=True), nullable=True),
    Column("is_valid", Boolean, nullable=False, default=True),
)


@dataclass
class DrillInstance:
    drill_instance_id: uuid.UUID
    user_id: uuid.UUID
    phone_number: str
    drill_slug: str
    current_prompt_slug: Optional[str] = None
    current_prompt_start_time: Optional[datetime.datetime] = None
    current_prompt_last_response_time: Optional[datetime.datetime] = None
    completion_time: Optional[datetime.datetime] = None
    is_valid: bool = True


class DrillInstanceRepository:
    def __init__(self, engine_factory=db.get_sqlalchemy_engine):
        self.engine_factory = engine_factory
        self.engine = engine_factory()

    def update_drill_instances(self, user_id: uuid.UUID, event: DialogEvent):
        if isinstance(event, UserValidated):
            self._invalidate_prior_drills(user_id)
        elif isinstance(event, DrillStarted):
            self._record_new_drill_instance(user_id, event)
        elif isinstance(event, DrillCompleted):
            self._mark_drill_instance_complete(event)
        elif isinstance(event, CompletedPrompt):
            self._update_current_prompt_response_time(event)
        elif isinstance(event, FailedPrompt):
            self._update_current_prompt_response_time(event)
        elif isinstance(event, AdvancedToNextPrompt):
            self._update_current_prompt(event)
        elif isinstance(event, ReminderTriggered) or isinstance(event, UserValidationFailed):
            logging.info(f"Ignoring event of type {event.event_type}")
        else:
            raise ValueError(f"Unknown event type {event.event_type}")

    def _invalidate_prior_drills(self, user_id: uuid.UUID):
        self.engine.execute(
            drill_instances.update()
            .where(drill_instances.c.user_id == func.uuid(str(user_id)))
            .values(is_valid=False)
        )

    def _record_new_drill_instance(self, user_id: uuid.UUID, event: DrillStarted):
        drill_instance = DrillInstance(
            drill_instance_id=event.drill_instance_id,
            user_id=user_id,
            phone_number=event.phone_number,
            drill_slug=event.drill.slug,
            current_prompt_slug=event.first_prompt.slug,
            current_prompt_start_time=event.created_time,
        )
        self.save_drill_instance(drill_instance)

    def _mark_drill_instance_complete(self, event: DrillCompleted):
        self.engine.execute(
            drill_instances.update()
            .where(drill_instances.c.drill_instance_id == func.uuid(str(event.drill_instance_id)))
            .values(
                completion_time=event.created_time,
                current_prompt_slug=None,
                current_prompt_start_time=None,
                current_prompt_last_response_time=None,
            )
        )

    def _update_current_prompt_response_time(self, event: Union[FailedPrompt, CompletedPrompt]):
        self.engine.execute(
            drill_instances.update()
            .where(drill_instances.c.drill_instance_id == func.uuid(str(event.drill_instance_id)))
            .values(current_prompt_last_response_time=event.created_time)
        )

    def _update_current_prompt(self, event: AdvancedToNextPrompt):
        self.engine.execute(
            drill_instances.update()
            .where(drill_instances.c.drill_instance_id == func.uuid(str(event.drill_instance_id)))
            .values(
                current_prompt_last_response_time=None,
                current_prompt_start_time=event.created_time,
                current_prompt_slug=event.prompt.slug,
            )
        )

    def _deserialize_row(self, row):
        return DrillInstance(
            drill_instance_id=uuid.UUID(row["drill_instance_id"]),
            user_id=uuid.UUID(row["user_id"]),
            phone_number=row["phone_number"],
            drill_slug=row["drill_slug"],
            current_prompt_slug=row["current_prompt_slug"],
            current_prompt_start_time=row["current_prompt_start_time"],
            current_prompt_last_response_time=row["current_prompt_last_response_time"],
            completion_time=row["completion_time"],
            is_valid=row["is_valid"],
        )

    def get_drill_instance(self, drill_instance_id: uuid.UUID) -> Optional[DrillInstance]:
        result = self.engine.execute(
            select([drill_instances]).where(
                drill_instances.c.drill_instance_id == func.uuid(str(drill_instance_id))
            )
        )
        row = result.fetchone()
        if row is None:
            return None
        return self._deserialize_row(row)

    def save_drill_instance(self, drill_instance: DrillInstance):
        settings = dict(
            current_prompt_slug=str(drill_instance.current_prompt_slug),
            current_prompt_start_time=drill_instance.current_prompt_start_time,
            current_prompt_last_response_time=drill_instance.current_prompt_last_response_time,
            completion_time=drill_instance.completion_time,
            is_valid=drill_instance.is_valid,
        )
        stmt = insert(drill_instances).values(
            drill_instance_id=str(drill_instance.drill_instance_id),
            user_id=str(drill_instance.user_id),
            phone_number=drill_instance.phone_number,
            drill_slug=str(drill_instance.drill_slug),
            **settings,
        )
        try:
            self.engine.execute(stmt)
        except IntegrityError:
            self.engine.execute(
                drill_instances.update()
                .where(
                    drill_instances.c.drill_instance_id
                    == func.uuid(str(drill_instance.drill_instance_id))
                )
                .values(**settings)
            )

    def get_incomplete_drills(self, inactive_for_minutes=None) -> List[DrillInstance]:
        stmt = select([drill_instances]).where(drill_instances.c.completion_time == None)
        if inactive_for_minutes is not None:
            stmt = stmt.where(
                drill_instances.c.current_prompt_start_time
                >= datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(minutes=-1 * inactive_for_minutes)
            )
        results = self.engine.execute(stmt)
        rows = results.fetchall()
        return [self._deserialize_row(row) for row in rows]

    def drop_and_recreate_tables_testing_only(self):
        if self.engine_factory == db.get_sqlalchemy_engine:
            raise ValueError("This function should not be called against databases in RDS")
        try:
            drill_instances.drop(bind=self.engine)
        except DatabaseError:
            pass
        metadata.create_all(bind=self.engine)
