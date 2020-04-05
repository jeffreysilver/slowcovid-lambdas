import uuid

from typing import List
import re

from sqlalchemy import (
    Table,
    MetaData,
    Column,
    String,
    select,
    insert,
)
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.exc import DatabaseError, IntegrityError

from stopcovid import db

metadata = MetaData()
messages = Table(
    "messages",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("twilio_message_id", String, nullable=False, index=True, unique=True),
    Column("from_number", String, nullable=True, index=True),
    Column("to_number", String, nullable=False, index=True),
    Column("body", String, nullable=False, index=True),
    Column("status", String, nullable=False, index=True),
)


class MessageRepository:
    def __init__(self, engine_factory=db.get_sqlalchemy_engine):
        self.engine_factory = engine_factory
        self.engine = engine_factory()

    def _integrity_error_is_dupe_twilio_message_id(self, exc):
        exp = "violates unique constraint .*twilio_message_id"
        return bool(re.search(exp, exc._sql_message(as_unicode=True)))

    def upsert_messages(self, values: List[dict]):
        def _prep_insert(obj):
            obj["id"] = uuid.uuid4()
            return obj

        with self.engine.connect() as connection:
            with connection.begin():
                for value in values:
                    try:
                        stmt = insert(messages).values(**_prep_insert(value))
                        self.engine.execute(stmt)
                    except IntegrityError as exception:
                        # If the upsert error was anything besides a duplicate twilio_message_id reraise
                        if not self._integrity_error_is_dupe_twilio_message_id(exception):
                            raise exception
                        twilio_message_id = value.pop("twilio_message_id")
                        stmt = (
                            messages.update()
                            .where(messages.c.twilio_message_id == twilio_message_id)
                            .values(**value)
                        )
                        self.engine.execute(stmt)

    def _get_messages(self):
        results = self.engine.execute(select([messages]))
        return [row for row in results]

    def drop_and_recreate_tables_testing_only(self):
        if self.engine_factory == db.get_sqlalchemy_engine:
            raise ValueError("This function should not be called against databases in RDS")
        try:
            messages.drop(bind=self.engine)
        except DatabaseError:
            pass

        metadata.create_all(bind=self.engine)
