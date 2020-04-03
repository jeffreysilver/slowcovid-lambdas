import datetime
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union

from sqlalchemy import (
    Table,
    MetaData,
    Column,
    String,
    ForeignKey,
    Boolean,
    DateTime,
    select,
    Integer,
    func,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.exc import DatabaseError

from . import db
from stopcovid.dialog.types import UserProfile, DialogEvent
from ..dialog.dialog import (
    UserValidated,
    DrillStarted,
    DrillCompleted,
    CompletedPrompt,
    FailedPrompt,
    AdvancedToNextPrompt,
    ReminderTriggered,
    UserValidationFailed,
)

ALL_DRILL_SLUGS = [
    "01-basics",
    "02-prevention",
    "03-hand-washing-how",
    "04-hand-sanitizer",
    "05-disinfect-phone",
    "06-hand-washing-when",
    "07-sanitizing-surfaces",
]

metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("user_id", UUID, primary_key=True),
    Column("account_info", JSONB, nullable=False),
    Column("last_interacted_time", DateTime(timezone=True)),
)

phone_numbers = Table(
    "phone_numbers",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("phone_number", String, nullable=False, unique=True),
    Column("user_id", UUID, ForeignKey("users.user_id"), nullable=False),
    Column("is_primary", Boolean, nullable=False),
)

drill_statuses = Table(
    "drill_statuses",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("user_id", UUID, ForeignKey("users.user_id"), nullable=False),
    Column("drill_instance_id", UUID, nullable=True, index=True),
    Column("drill_slug", String, nullable=False),
    Column("place_in_sequence", Integer, nullable=False),
    Column("started_time", DateTime(timezone=True)),
    Column("completed_time", DateTime(timezone=True)),
    UniqueConstraint("user_id", "place_in_sequence"),
)


@dataclass
class User:
    user_id: UUID = field(default_factory=uuid.uuid4)
    account_info: Dict[str, Any] = field(default_factory=dict)
    last_interacted_time: Optional[datetime.datetime] = None


@dataclass
class PhoneNumber:
    phone_number: str
    user_id: UUID
    is_primary: bool = True
    id: UUID = field(default_factory=uuid.uuid4)


@dataclass
class DrillStatus:
    id: uuid.UUID
    user_id: uuid.UUID
    drill_instance_id: uuid.UUID
    drill_slug: str
    place_in_sequence: int
    started_time: datetime.datetime
    completed_time: datetime.datetime


class UserRepository:
    def __init__(self, engine_factory=db.get_sqlalchemy_engine):
        self.engine_factory = engine_factory
        self.engine = engine_factory()

    def get_user(self, user_id: uuid.UUID) -> Optional[User]:
        result = self.engine.execute(
            select([users]).where(users.c.user_id == func.uuid(str(user_id)))
        )
        row = result.fetchone()
        if row is None:
            return None
        return User(
            user_id=uuid.UUID(row["user_id"]),
            account_info=row["account_info"],
            last_interacted_time=row["last_interacted_time"],
        )

    def get_drill_status(self, user_id: uuid.UUID, drill_slug: str) -> Optional[DrillStatus]:
        result = self.engine.execute(
            select([drill_statuses]).where(
                drill_statuses.c.user_id == func.uuid(str(user_id))
                and drill_statuses.c.drill_slug == drill_slug
            )
        )
        row = result.fetchone()
        if row is None:
            return None
        return DrillStatus(
            id=uuid.UUID(row["id"]),
            user_id=uuid.UUID(row["user_id"]),
            drill_instance_id=uuid.UUID(row["drill_instance_id"]),
            drill_slug=row["drill_slug"],
            place_in_sequence=row["place_in_sequence"],
            started_time=row["started_time"],
            completed_time=row["completed_time"],
        )

    def update_user_progress(self, user_id: uuid.UUID, event: DialogEvent):
        if isinstance(event, UserValidated):
            self._reset_drill_statuses(user_id)
        elif isinstance(event, DrillStarted):
            self._mark_drill_started(user_id, event)
        elif isinstance(event, DrillCompleted):
            self._mark_drill_completed(user_id, event)
        elif isinstance(event, CompletedPrompt):
            self._mark_interaction_time(user_id, event)
        elif isinstance(event, FailedPrompt):
            self._mark_interaction_time(user_id, event)
        elif (
            isinstance(event, AdvancedToNextPrompt)
            or isinstance(event, ReminderTriggered)
            or isinstance(event, UserValidationFailed)
            or isinstance(event, AdvancedToNextPrompt)
        ):
            logging.info(f"Ignoring event of type {event.event_type}")
        else:
            raise ValueError(f"Unknown event type {event.event_type}")

    def create_or_update_user(self, phone_number: str, profile: UserProfile) -> uuid.UUID:

        with self.engine.connect() as connection:
            with connection.begin():
                result = connection.execute(
                    select([phone_numbers]).where(phone_numbers.c.phone_number == phone_number)
                )
                row = result.fetchone()
                if row is None:
                    user_record = User(account_info=profile.account_info)
                    phone_number_record = PhoneNumber(
                        phone_number=phone_number, user_id=user_record.user_id
                    )
                    connection.execute(
                        users.insert().values(
                            user_id=str(user_record.user_id), account_info=user_record.account_info
                        )
                    )
                    connection.execute(
                        phone_numbers.insert().values(
                            id=str(phone_number_record.id),
                            user_id=str(phone_number_record.user_id),
                            is_primary=phone_number_record.is_primary,
                            phone_number=phone_number_record.phone_number,
                        )
                    )
                    for i, slug in enumerate(ALL_DRILL_SLUGS):
                        connection.execute(
                            drill_statuses.insert().values(
                                id=str(uuid.uuid4()),
                                user_id=str(user_record.user_id),
                                drill_slug=slug,
                                place_in_sequence=i,
                            )
                        )
                    return user_record.user_id
                phone_number_record = PhoneNumber(**row)
                connection.execute(
                    users.update()
                    .where(users.c.user_id == func.uuid(str(phone_number_record.user_id)))
                    .values(account_info=profile.account_info)
                )
                return phone_number_record.user_id

    def _reset_drill_statuses(self, user_id: uuid.UUID):
        self.engine.execute(
            drill_statuses.update()
            .where(drill_statuses.c.user_id == func.uuid(str(user_id)))
            .values(started_time=None, completed_time=None)
        )

    def _mark_drill_started(self, user_id: uuid.UUID, event: DrillStarted):
        self.engine.execute(
            drill_statuses.update()
            .where(
                drill_statuses.c.user_id == func.uuid(str(user_id))
                and drill_statuses.c.drill_slug == event.drill.slug
            )
            .values(started_time=event.created_time, drill_instance_id=str(event.drill_instance_id))
        )

    def _mark_drill_completed(self, user_id: uuid.UUID, event: DrillCompleted):
        self.engine.execute(
            drill_statuses.update()
            .where(
                drill_statuses.c.user_id == func.uuid(str(user_id))
                and drill_statuses.c.drill_instance_id == func.uuid(str(event.drill_instance_id))
            )
            .values(completed_time=event.created_time)
        )

    def _mark_interaction_time(self, user_id, event: Union[CompletedPrompt, FailedPrompt]):
        self.engine.execute(
            users.update()
            .where(users.c.user_id == func.uuid(str(user_id)))
            .values(last_interacted_time=event.created_time)
        )

    def drop_and_recreate_tables_testing_only(self):
        if self.engine_factory == db.get_sqlalchemy_engine:
            raise ValueError("This function should not be called against databases in RDS")
        try:
            drill_statuses.drop(bind=self.engine)
        except DatabaseError:
            pass
        try:
            phone_numbers.drop(bind=self.engine)
        except DatabaseError:
            pass
        try:
            users.drop(bind=self.engine)
        except DatabaseError:
            pass
        metadata.create_all(bind=self.engine)
