import uuid
from dataclasses import dataclass
from typing import List
import logging

from sqlalchemy import (
    Table,
    MetaData,
    Column,
    String,
    select,
    exists,
    and_,
    insert,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.exc import DatabaseError, IntegrityError

from . import db

metadata = MetaData()
reminder_triggers = Table(
    "reminder_triggers",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("drill_instance_id", UUID, nullable=False, index=True),
    Column("prompt_slug", String, nullable=False),
    # Do not remind for same prompt on drill twice
    UniqueConstraint("drill_instance_id", "prompt_slug"),
)


@dataclass
class ReminderTrigger:
    id: uuid.UUID
    drill_instance_id: uuid.UUID
    prompt_slug: str

    def serialize(self):
        return {
            "id": str(self.id),
            "drill_instance_id": str(self.drill_instance_id),
            "prompt_slug": self.prompt_slug,
        }


class ReminderTriggerRepository:
    def __init__(self, engine_factory=db.get_sqlalchemy_engine):
        self.engine_factory = engine_factory
        self.engine = engine_factory()

    def _deserialize(self, row):
        return ReminderTrigger(
            id=uuid.UUID(row["id"]),
            drill_instance_id=uuid.UUID(row["drill_instance_id"]),
            prompt_slug=row["prompt_slug"],
        )

    def save_reminder_triggers(self, values: List[ReminderTrigger]):
        with self.engine.connect() as connection:
            with connection.begin():
                for value in values:
                    stmt = insert(reminder_triggers).values(
                        id=str(value.id),
                        drill_instance_id=str(value.drill_instance_id),
                        prompt_slug=value.prompt_slug,
                    )
                    try:
                        self.engine.execute(stmt)
                    except IntegrityError:
                        logging.info(
                            "Reprocessing a reminder_trigger instance that was already "
                            f"created {value.id}. Ignoring."
                        )

    def get_reminder_triggers(self):
        results = self.engine.execute(select([reminder_triggers]))
        return [self._deserialize(row) for row in results]

    def reminder_trigger_exists(self, drill_instance_id, prompt_slug):
        return self.engine.execute(
            exists([reminder_triggers])
            .where(
                and_(
                    reminder_triggers.c.drill_instance_id == str(drill_instance_id),
                    reminder_triggers.c.prompt_slug == prompt_slug,
                )
            )
            .select()
        ).scalar()

    def drop_and_recreate_tables_testing_only(self):
        if self.engine_factory == db.get_sqlalchemy_engine:
            raise ValueError("This function should not be called against databases in RDS")
        try:
            reminder_triggers.drop(bind=self.engine)
        except DatabaseError:
            pass

        metadata.create_all(bind=self.engine)
