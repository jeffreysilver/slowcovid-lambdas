import os
import boto3

def insert_message(twilio_message_id, body, from_phone, to_phone, approximate_arrival_timestamp, sequence_number):
    sql = """
          insert into message (twilio_message_id, body, from_phone, to_phone, approximate_arrival_timestamp, sequence_number) 
          values (:twilio_message_id, :body, :from_phone, :to_phone, :approximate_arrival_timestamp, :sequence_number);
          """
    sql_params = [
        {'name': 'twilio_message_id', 'value': {'stringValue': twilio_message_id}},
        {'name': 'body', 'value': {'stringValue': body}},
        {'name': 'from_phone', 'value': {'stringValue': from_phone}},
        {'name': 'to_phone', 'value': {'stringValue': to_phone}},
        {'name': 'approximate_arrival_timestamp', 'value': {'stringValue': str(approximate_arrival_timestamp)}},
        {'name': 'sequence_number', 'value': {'stringValue': sequence_number}},
    ]

    db_cluster_arn = os.environ.get("DB_CLUSTER_ARN")
    db_credentials_secret_arn = os.environ.get("DB_SECRET_ARN")
    
    rds_client = boto3.client('rds-data')
    
    return rds_client.execute_statement(
        secretArn=db_credentials_secret_arn,
        database="postgres",
        resourceArn=db_cluster_arn,
        sql=sql,
        parameters=sql_params
    )