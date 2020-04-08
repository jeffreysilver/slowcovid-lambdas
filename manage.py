import argparse
import sys
import uuid

import boto3
from sqlalchemy import create_engine, select, func


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

    aurora_info = {
        "dev": {
            "secret_arn": "arn:aws:secretsmanager:us-east-1:696991354966:secret:rds-db-credentials/cluster-4ZVDIMJW7RR5MVI4FQNFMNK4TQ/postgres-wIfT7f",
            "cluster_arn": "arn:aws:rds:us-east-1:696991354966:cluster:dev",
        },
        "prod": {
            "secret_arn": "arn:aws:secretsmanager:us-east-1:696991354966:secret:rds-db-credentials/cluster-PQD3BD7IFQ2QK33XBKIFSXANUQ/postgres-8WXal2",
            "cluster_arn": "arn:aws:rds:us-east-1:696991354966:cluster:prod",
        },
    }

    engine = create_engine(
        "postgresql+auroradataapi://:@/postgres",
        connect_args=dict(
            aurora_cluster_arn=aurora_info[args.stage]["cluster_arn"],
            secret_arn=aurora_info[args.stage]["secret_arn"],
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

    args = parser.parse_args(sys.argv if len(sys.argv) == 1 else None)
    args.func(args)


if __name__ == "__main__":
    main()
