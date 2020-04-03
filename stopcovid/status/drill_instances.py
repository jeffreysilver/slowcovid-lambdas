import datetime
import logging
import uuid
from dataclasses import dataclass
from typing import Union, Optional

from sqlalchemy import (
    MetaData,
    Table,
    Column,
    String,
    DateTime,
    Boolean,
    select,
    func,
    insert,
    and_,
)
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
from stopcovid.dialog.types import DialogEventBatch
from . import db

metadata = MetaData()
drill_instances = Table(
    "drill_instances",
    metadata,
    Column("drill_instance_id", UUID, primary_key=True),
    Column("user_id", UUID, nullable=False),
    Column("seq", String, nullable=False),
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
    seq: str
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

    def update_drill_instances(self, user_id: uuid.UUID, batch: DialogEventBatch):
        with self.engine.connect() as connection:
            with connection.begin():
                for event in batch.events:
                    if isinstance(event, UserValidated):
                        self._invalidate_prior_drills(user_id, batch.seq, connection)
                    elif isinstance(event, DrillStarted):
                        self._record_new_drill_instance(user_id, event, batch.seq, connection)
                    elif isinstance(event, DrillCompleted):
                        self._mark_drill_instance_complete(event, batch.seq, connection)
                    elif isinstance(event, CompletedPrompt):
                        self._update_current_prompt_response_time(event, batch.seq, connection)
                    elif isinstance(event, FailedPrompt):
                        self._update_current_prompt_response_time(event, batch.seq, connection)
                    elif isinstance(event, AdvancedToNextPrompt):
                        self._update_current_prompt(event, batch.seq, connection)
                    elif isinstance(event, ReminderTriggered) or isinstance(
                        event, UserValidationFailed
                    ):
                        logging.info(f"Ignoring event of type {event.event_type}")
                    else:
                        raise ValueError(f"Unknown event type {event.event_type}")

    @staticmethod
    def _invalidate_prior_drills(user_id: uuid.UUID, batch_seq: str, connection):
        ids = set()
        result = connection.execute(
            select([drill_instances.c.drill_instance_id, drill_instances.c.seq]).where(
                and_(
                    drill_instances.c.user_id == func.uuid(str(user_id)),
                    drill_instances.c.is_valid.is_(True),
                )
            )
        )
        for row in result:
            row_seq = int(row["seq"])
            if row_seq < int(batch_seq):
                ids.add(row["drill_instance_id"])

        connection.execute(
            drill_instances.update()
            .where(drill_instances.c.drill_instance_id.in_(ids))
            .values(is_valid=False)
        )

    def _record_new_drill_instance(
        self, user_id: uuid.UUID, event: DrillStarted, seq: str, connection
    ):
        drill_instance = DrillInstance(
            drill_instance_id=event.drill_instance_id,
            seq=seq,
            user_id=user_id,
            phone_number=event.phone_number,
            drill_slug=event.drill.slug,
            current_prompt_slug=event.first_prompt.slug,
            current_prompt_start_time=event.created_time,
        )
        self._save_drill_instance(drill_instance, connection)

    def _mark_drill_instance_complete(self, event: DrillCompleted, seq: str, connection):
        if self._is_not_stale(event.drill_instance_id, seq, connection):
            connection.execute(
                drill_instances.update()
                .where(
                    drill_instances.c.drill_instance_id == func.uuid(str(event.drill_instance_id))
                )
                .values(
                    completion_time=event.created_time,
                    current_prompt_slug=None,
                    current_prompt_start_time=None,
                    current_prompt_last_response_time=None,
                )
            )

    def _update_current_prompt_response_time(
        self, event: Union[FailedPrompt, CompletedPrompt], seq: str, connection
    ):
        if self._is_not_stale(event.drill_instance_id, seq, connection):
            connection.execute(
                drill_instances.update()
                .where(
                    drill_instances.c.drill_instance_id == func.uuid(str(event.drill_instance_id))
                )
                .values(current_prompt_last_response_time=event.created_time)
            )

    def _update_current_prompt(self, event: AdvancedToNextPrompt, seq: str, connection):
        if self._is_not_stale(event.drill_instance_id, seq, connection):
            connection.execute(
                drill_instances.update()
                .where(
                    drill_instances.c.drill_instance_id == func.uuid(str(event.drill_instance_id))
                )
                .values(
                    current_prompt_last_response_time=None,
                    current_prompt_start_time=event.created_time,
                    current_prompt_slug=event.prompt.slug,
                )
            )

    def get_drill_instance(
        self, drill_instance_id: uuid.UUID, connection=None
    ) -> Optional[DrillInstance]:
        if connection is None:
            connection = self.engine
        result = connection.execute(
            select([drill_instances]).where(
                drill_instances.c.drill_instance_id == func.uuid(str(drill_instance_id))
            )
        )
        row = result.fetchone()
        if row is None:
            return None
        return DrillInstance(
            drill_instance_id=uuid.UUID(row["drill_instance_id"]),
            seq=row["seq"],
            user_id=uuid.UUID(row["user_id"]),
            phone_number=row["phone_number"],
            drill_slug=row["drill_slug"],
            current_prompt_slug=row["current_prompt_slug"],
            current_prompt_start_time=row["current_prompt_start_time"],
            current_prompt_last_response_time=row["current_prompt_last_response_time"],
            completion_time=row["completion_time"],
            is_valid=row["is_valid"],
        )

    def _is_not_stale(self, drill_instance_id: uuid.UUID, seq: str, connection):
        drill_instance = self.get_drill_instance(drill_instance_id, connection=connection)
        return int(seq) > int(drill_instance.seq)

    def _save_drill_instance(self, drill_instance: DrillInstance, connection=None):
        if connection is None:
            connection = self.engine
        stmt = insert(drill_instances).values(
            drill_instance_id=str(drill_instance.drill_instance_id),
            user_id=str(drill_instance.user_id),
            phone_number=drill_instance.phone_number,
            drill_slug=str(drill_instance.drill_slug),
            current_prompt_slug=str(drill_instance.current_prompt_slug),
            current_prompt_start_time=drill_instance.current_prompt_start_time,
            current_prompt_last_response_time=drill_instance.current_prompt_last_response_time,
            completion_time=drill_instance.completion_time,
            is_valid=drill_instance.is_valid,
            seq=drill_instance.seq,
        )
        try:
            connection.execute(stmt)
        except IntegrityError:
            logging.info(
                f"Reprocessing a drill instance that was already "
                f"created {drill_instance.drill_instance_id}. Ignoring."
            )

    def drop_and_recreate_tables_testing_only(self):
        if self.engine_factory == db.get_sqlalchemy_engine:
            raise ValueError("This function should not be called against databases in RDS")
        try:
            drill_instances.drop(bind=self.engine)
        except DatabaseError:
            pass
        metadata.create_all(bind=self.engine)
