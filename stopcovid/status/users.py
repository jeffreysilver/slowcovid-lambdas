import json
import uuid

from stopcovid.clients import rds
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


def create_or_update_user(phone_number: str, profile: UserProfile, engine=None) -> uuid.UUID:
    if engine is None:
        engine = rds.get_sqlalchemy_engine()

    account_info = json.dumps(profile.account_info or {})

    with engine.connect() as connection:
        result = connection.execute(
            "select id, user_id from phone_numbers where phone_number=:phone_number",
            phone_number=phone_number,
        )
        for row in result:
            user_id = row["user_id"]
            connection.execute(
                "update users set account_info=cast(:account_info as jsonb) "
                "where user_id=uuid(:user_id)",
                user_id=user_id,
                account_info=account_info,
            )
            return uuid.UUID(user_id)

        with connection.begin():
            user_id = uuid.uuid4()
            connection.execute(
                "insert into users (user_id, account_info) "
                "values(uuid(:user_id), cast(:account_info as jsonb));",
                user_id=str(user_id),
                account_info=account_info,
            )
            connection.execute(
                "insert into phone_numbers (id, phone_number, user_id, is_primary) "
                "values (uuid(:id), :phone_number, uuid(:user_id), true);",
                id=str(uuid.uuid4()),
                phone_number=phone_number,
                user_id=str(user_id),
            )
            return user_id


def ensure_tables_exist(engine=None):
    if engine is None:
        engine = rds.get_sqlalchemy_engine()
    engine.execute(
        """
        create table if not exists users (
            user_id uuid,
            account_info jsonb not null,
            primary key (user_id)
        );
        """
    )
    engine.execute(
        """
        create table if not exists phone_numbers (
            id uuid,
            phone_number text unique not null,
            user_id uuid not null references users(user_id),
            is_primary bool not null,
            primary key (id)
        );
        """
    )
