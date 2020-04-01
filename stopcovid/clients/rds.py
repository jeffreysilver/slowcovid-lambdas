import os
import boto3
from sqlalchemy import create_engine

RDS = boto3.client("rds-data")


def insert_message(twilio_message_id, body, from_phone, to_phone, status):
    sql = """
        insert into
        message (
            twilio_message_id,
            body,
            from_phone,
            to_phone,
            status
        )
        values (
            :twilio_message_id,
            :body,
            :from_phone,
            :to_phone,
            :status
        );
    """

    sql_params = [
        {"name": "twilio_message_id", "value": {"stringValue": twilio_message_id}},
        {"name": "body", "value": {"stringValue": body}},
        {
            "name": "from_phone",
            "value": {"stringValue": from_phone} if from_phone else {"isNull": True},
        },
        {"name": "to_phone", "value": {"stringValue": to_phone}},
        {"name": "status", "value": {"stringValue": status}},
    ]

    db_cluster_arn = os.environ.get("DB_CLUSTER_ARN")
    db_credentials_secret_arn = os.environ.get("DB_SECRET_ARN")

    return RDS.execute_statement(
        secretArn=db_credentials_secret_arn,
        database="postgres",
        resourceArn=db_cluster_arn,
        sql=sql,
        parameters=sql_params,
    )


def update_message(twilio_message_id, status, from_phone):
    sql = f"UPDATE message SET status='{status}', from_phone='{from_phone}' WHERE twilio_message_id='{twilio_message_id}'"

    db_cluster_arn = os.environ.get("DB_CLUSTER_ARN")
    db_credentials_secret_arn = os.environ.get("DB_SECRET_ARN")

    return RDS.execute_statement(
        secretArn=db_credentials_secret_arn,
        database="postgres",
        resourceArn=db_cluster_arn,
        sql=sql,
    )


def get_sqlalchemy_engine():
    cluster_arn = os.environ.get("DB_CLUSTER_ARN")
    secret_arn = os.environ.get("DB_SECRET_ARN")
    return create_engine(
        "postgresql+auroradataapi://:@/postgres",
        echo=True,
        connect_args=dict(aurora_cluster_arn=cluster_arn, secret_arn=secret_arn),
    )
