import datetime
import uuid
from dataclasses import dataclass
from typing import Union, Optional

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
)
from stopcovid.dialog.types import DialogEvent
from . import db

metadata = MetaData()
drill_instances = Table(
    "drill_instances",
    metadata,
    Column("drill_instance_id", UUID, primary_key=True),
    Column("user_id", UUID, nullable=False),
    Column("drill_slug", String, nullable=False),
    Column("current_prompt_slug", String, nullable=True),
    Column("current_prompt_start_time", DateTime, nullable=True),
    Column("current_prompt_last_response_time", DateTime, nullable=True),
    Column("is_complete", Boolean, nullable=False, default=False),
    Column("is_valid", Boolean, nullable=False, default=True),
)


@dataclass
class DrillInstance:
    drill_instance_id: uuid.UUID
    user_id: uuid.UUID
    drill_slug: str
    current_prompt_slug: Optional[str] = None
    current_prompt_start_time: Optional[datetime.datetime] = None
    current_prompt_last_response_time: Optional[datetime.datetime] = None
    is_complete: bool = False
    is_valid: bool = True


class DrillInstanceRepository:
    def __init__(self, engine_factory=db.get_sqlalchemy_engine):
        self.engine_factory = engine_factory
        self.engine = engine_factory()

    def update_drill_instances(self, user_id: uuid.UUID, event: DialogEvent):
        if isinstance(event, UserValidated):
            self.invalidate_prior_drills(user_id)
        if isinstance(event, DrillStarted):
            self.record_new_drill_instance(user_id, event)
        if isinstance(event, DrillCompleted):
            self.mark_drill_instance_complete(user_id, event)
        if isinstance(event, CompletedPrompt):
            self.update_current_prompt_response_time(user_id, event)
        if isinstance(event, FailedPrompt):
            self.update_current_prompt_response_time(user_id, event)
        if isinstance(event, AdvancedToNextPrompt):
            self.update_current_prompt(user_id, event)

    def invalidate_prior_drills(self, user_id: uuid.UUID):
        pass

    def record_new_drill_instance(self, user_id: uuid.UUID, event: DrillStarted):
        pass

    def mark_drill_instance_complete(self, user_id: uuid.UUID, event: DrillCompleted):
        pass

    def update_current_prompt_response_time(
        self, user_id: uuid.UUID, event: Union[FailedPrompt, CompletedPrompt]
    ):
        pass

    def update_current_prompt(self, user_id: uuid.UUID, event: AdvancedToNextPrompt):
        pass

    def get_drill_instance(self, drill_instance_id: uuid.UUID) -> Optional[DrillInstance]:
        result = self.engine.execute(
            select([drill_instances]).where(
                drill_instances.c.drill_instance_id == func.uuid(str(drill_instance_id))
            )
        )
        row = result.fetchone()
        if row is None:
            return None
        return DrillInstance(
            drill_instance_id=uuid.UUID(row["drill_instance_id"]),
            user_id=uuid.UUID(row["user_id"]),
            drill_slug=row["drill_slug"],
            current_prompt_slug=row["current_prompt_slug"],
            current_prompt_start_time=row["current_prompt_start_time"],
            current_prompt_last_response_time=row["current_prompt_last_response_time"],
            is_complete=row["is_complete"],
            is_valid=row["is_valid"],
        )

    def save_drill_instance(self, drill_instance: DrillInstance):
        settings = dict(
            current_prompt_slug=str(drill_instance.current_prompt_slug),
            current_prompt_start_time=drill_instance.current_prompt_start_time,
            current_prompt_last_response_time=drill_instance.current_prompt_last_response_time,
            is_complete=drill_instance.is_complete,
            is_valid=drill_instance.is_valid,
        )
        stmt = insert(drill_instances).values(
            drill_instance_id=str(drill_instance.drill_instance_id),
            user_id=str(drill_instance.user_id),
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

    def drop_and_recreate_tables_testing_only(self):
        if self.engine_factory == db.get_sqlalchemy_engine:
            raise ValueError("This function should not be called against databases in RDS")
        try:
            drill_instances.drop(bind=self.engine)
        except DatabaseError:
            pass
        metadata.create_all(bind=self.engine)
