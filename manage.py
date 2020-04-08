import argparse
import sys
import uuid
from typing import Iterator

import boto3
from sqlalchemy import create_engine, select, func

from stopcovid.dialog.models.events import batch_from_dict, DialogEventBatch
from stopcovid.status.drill_progress import DrillProgressRepository
from stopcovid.utils import dynamodb as dynamodb_utils
from stopcovid.utils.logging import configure_logging

configure_logging()


def get_env(stage: str):
    filename = {"dev": ".env.development", "prod": ".env.production"}[stage]
    with open(filename) as file:
        return {
            line_part[0].strip(): line_part[1].strip()
            for line_part in (line.split("=") for line in file.readlines())
        }


def handle_redrive_sqs(args):
    sqs = boto3.resource("sqs")

    queue_configs = {
        "sms": {
            "queue": f"outbound-sms-{args.stage}.fifo",
            "dlq": f"outbound-sms-dlq-{args.stage}.fifo",
        },
        "drill-initiation": {
            "queue": f"drill-initiation-{args.stage}",
            "dlq": f"drill-initiation-dlq-{args.stage}",
        },
    }
    queue_config = queue_configs[args.queue]

    queue = sqs.get_queue_by_name(QueueName=queue_config["queue"])
    dlq = sqs.get_queue_by_name(QueueName=queue_config["dlq"])

    total_redriven = 0
    while True:
        messages = dlq.receive_messages(WaitTimeSeconds=1)
        if not messages:
            print(
                f"Redrove {total_redriven} message{'s' if total_redriven != 1 else ''} from the dlq"
            )
            return
        queue.send_messages(
            Entries=[
                {
                    "MessageBody": message.body,
                    "MessageAttributes": message.message_attributes or {},
                    "Id": str(uuid.uuid4()),
                }
                for message in messages
            ]
        )
        for message in messages:
            message.delete()
        total_redriven += len(messages)


def handle_clear_seq(args):
    dynamodb_table_name = f"dialog-state-{args.stage}"
    dynamodb = boto3.client("dynamodb")
    key = {"phone_number": {"S": args.phone_number}}
    dynamodb.update_item(
        TableName=dynamodb_table_name,
        Key=key,
        UpdateExpression="SET seq = :seq",
        ExpressionAttributeValues={":seq": {"S": "0"}},
    )

    engine = create_engine(
        "postgresql+auroradataapi://:@/postgres",
        connect_args=dict(
            aurora_cluster_arn=get_env(args.stage)["DB_CLUSTER_ARN"],
            secret_arn=get_env(args.stage)["DB_SECRET_ARN"],
        ),
    )

    from stopcovid.status.drill_progress import users, phone_numbers

    row = engine.execute(
        select([users.c.user_id]).where(phone_numbers.c.phone_number == args.phone_number)
    ).fetchone()
    engine.execute(
        users.update().where(users.c.user_id == func.uuid(row["user_id"])).values(seq="0")
    )
    print("Done")


def _get_dialog_events(phone_number: str, stage: str) -> Iterator[DialogEventBatch]:
    dynamodb = boto3.client("dynamodb")
    table_name = f"dialog-event-batches-{stage}"
    args = {}
    while True:
        result = dynamodb.query(
            TableName=table_name,
            IndexName="by_created_time",
            KeyConditionExpression="phone_number=:phone_number",
            ExpressionAttributeValues={":phone_number": {"S": phone_number}},
            **args,
        )
        for item in result["Items"]:
            yield batch_from_dict(dynamodb_utils.deserialize(item))
        if not result.get("LastEvaluatedKey"):
            break
        args["ExclusiveStartKey"] = result["LastEvaluatedKey"]


def rebuild_drill_progress(args):
    environment = get_env(args.stage)
    engine_factory = lambda: create_engine(
        "postgresql+auroradataapi://:@/postgres",
        connect_args=dict(
            aurora_cluster_arn=environment["DB_CLUSTER_ARN"],
            secret_arn=environment["DB_SECRET_ARN"],
        ),
    )
    user_repo = DrillProgressRepository(engine_factory)
    for batch in _get_dialog_events(args.phone_number, args.stage):
        print(batch.seq)
        user_repo.update_user(batch)
    print("Done")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["dev", "prod"], required=True)
    subparsers = parser.add_subparsers(
        required=True, title="subcommands", description="valid subcommands"
    )
    sqs_parser = subparsers.add_parser(
        "redrive-sqs", description="Retry failures from an SQS queue"
    )
    sqs_parser.add_argument("queue", choices=["sms", "drill-initiation"])
    sqs_parser.set_defaults(func=handle_redrive_sqs)

    clear_seq_parser = subparsers.add_parser(
        "clear-seq",
        description="Reset sequence numbers for a user so that older commands can be processed",
    )
    clear_seq_parser.add_argument("phone_number")
    clear_seq_parser.set_defaults(func=handle_clear_seq)

    rebuild_status_parser = subparsers.add_parser(
        "rebuild-drill-progress",
        description="rebuild drill progress information for the user in aurora (may require"
        "clear-seq to be run first)",
    )
    rebuild_status_parser.add_argument("phone_number")
    rebuild_status_parser.set_defaults(func=rebuild_drill_progress)

    args = parser.parse_args(sys.argv if len(sys.argv) == 1 else None)
    args.func(args)


if __name__ == "__main__":
    main()
