import datetime
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

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
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.exc import DatabaseError

from . import db
from stopcovid.dialog.types import UserProfile

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
    Column("last_interacted_time", DateTime),
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
    Column("drill_slug", String, nullable=False),
    Column("place_in_sequence", Integer, nullable=False),
    Column("started_time", DateTime),
    Column("completed_time", DateTime),
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


def create_or_update_user(
    phone_number: str, profile: UserProfile, engine_factory=db.get_sqlalchemy_engine
) -> UUID:
    engine = engine_factory()

    with engine.connect() as connection:
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


def get_user(user_id: UUID, engine_factory=db.get_sqlalchemy_engine):
    engine = engine_factory()
    result = engine.execute(select([users]).where(users.c.user_id == func.uuid(str(user_id))))
    row = result.fetchone()
    if row is None:
        return None
    return User(
        user_id=uuid.UUID(row["user_id"]),
        account_info=row["account_info"],
        last_interacted_time=row["last_interacted_time"],
    )


def drop_and_recreate_tables_testing_only(engine_factory):
    if engine_factory == db.get_sqlalchemy_engine:
        raise ValueError("This function should not be called against databases in RDS")
    engine = engine_factory()
    try:
        drill_statuses.drop(bind=engine)
    except DatabaseError:
        pass
    try:
        phone_numbers.drop(bind=engine)
    except DatabaseError:
        pass
    try:
        users.drop(bind=engine)
    except DatabaseError:
        pass
    metadata.create_all(bind=engine)
