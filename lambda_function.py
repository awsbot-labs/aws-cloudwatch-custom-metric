from __future__ import print_function

import json
import boto3
import logging
import datetime
from datetime import datetime, timedelta, tzinfo
import os
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.info('Loading function')

response = boto3.client('sts').assume_role(
    RoleArn=os.environ['STS_ASSUME_ROLE_ARN'],
    RoleSessionName='CloudWatchCustomMetrics__CodeCommits-{}'.format(uuid.uuid4().hex[:10])
)

session = boto3.Session(
    aws_access_key_id=response['Credentials']['AccessKeyId'],
    aws_secret_access_key=response['Credentials']['SecretAccessKey'],
    aws_session_token=response['Credentials']['SessionToken'],
    region_name='eu-west-1'
)

dynamodb = session.client('dynamodb')


class FixedOffset(tzinfo):
    """offset_str: Fixed offset in str: e.g. '-04:00'"""

    def __init__(self, offset_str):
        sign, hours, minutes = offset_str[0], offset_str[1:2], offset_str[4:]
        offset = (int(hours) * 60 + int(minutes)) * (-1 if sign == "-" else 1)
        self.__offset = timedelta(minutes=offset)
        # NOTE: the last part is to remind about deprecated POSIX GMT+h timezones
        # that have the opposite sign in the name;
        # the corresponding numeric value is not used e.g., no minutes
        '<%+03d%02d>%+d' % (int(hours), int(minutes), int(hours) * -1)

    def utcoffset(self, dt=None):
        return self.__offset

    def tzname(self, dt=None):
        return self.__name

    def dst(self, dt=None):
        return timedelta(0)

    def __repr__(self):
        return 'FixedOffset(%d)' % (self.utcoffset().total_seconds() / 60)


def process_datetime(datetime_object, unix=False):
    dt_utc = datetime.strptime(datetime_object, '%Y-%m-%dT%H:%M:%SZ')
    if unix == True:
        return datetime.strftime(dt_utc, '%s').__str__()
    else:
        return datetime.strftime(dt_utc, '%Y-%m-%dT%H:%M:%SZ').__str__()


def lambda_handler(event, context):
    try:
        print(event)

        commit = boto3.client('codecommit').get_commit(
            repositoryName=event['detail']['repositoryName'],
            commitId=event['detail']['commitId']
        )

        response = boto3.client('cloudwatch').put_metric_data(
            Namespace='CodeCommit',
            MetricData=[
                {
                    'MetricName': 'RepoStateChange',
                    'Dimensions': [
                        {
                            'Name': 'id',
                            'Value': event['id'],
                        },
                        {
                            'Name': 'account',
                            'Value': event['account'],
                        },
                        {
                            'Name': 'region',
                            'Value': event['region'],
                        },
                        {
                            'Name': 'time',
                            'Value': event['time'],
                        },
                        {
                            'Name': 'repositoryName',
                            'Value': event['detail']['repositoryName'],
                        },
                        {
                            'Name': 'referenceType',
                            'Value': event['detail']['referenceType'],
                        },
                        {
                            'Name': 'referenceName',
                            'Value': event['detail']['referenceName'],
                        },
                        {
                            'Name': 'commitId',
                            'Value': event['detail']['commitId'],
                        },
                        {
                            'Name': 'repositoryId',
                            'Value': event['detail']['repositoryId'],
                        },
                    ],
                    'Timestamp': datetime.strptime(event['time'], "%Y-%m-%dT%H:%M:%SZ"),
                    'StatisticValues': {
                        'SampleCount': 1.0,
                        'Sum': 1.0,
                        'Minimum': 1.0,
                        'Maximum': 1.0
                    },
                    'Unit': 'None',
                    'StorageResolution': 60
                },
            ]
        )

        print(response)

        Item = {
                'id': {
                    'S': event['id']
                },
                'account': {
                    'S': event['account'],
                },
                'region': {
                    'S': event['region'],
                },
                '__typename': {
                    'S': 'Commit'
                },
                'createdAt': {
                    'S': process_datetime(event['time'])
                },
                'createdAtUnixTimeStamp': {
                    'S': process_datetime(event['time'], True)
                },
                'committer': {
                    'M': {
                        'date': {'S': commit['commit']['committer']['date']},
                        'name': {'S': commit['commit']['committer']['name']},
                        'email': {'S': commit['commit']['committer']['email']},
                    }
                },
                'author': {
                    'M': {
                        'date': {'S': commit['commit']['author']['date']},
                        'name': {'S': commit['commit']['author']['name']},
                        'email': {'S': commit['commit']['author']['email']},
                    }
                },
                'commitId': {
                    'S': commit['commit']['commitId']
                },
                'treeId': {
                    'S': commit['commit']['treeId']
                },
                'commitMessage': {
                    'S': commit['commit']['message']
                },
                'repositoryName': {
                    'S': event['detail']['repositoryName'],
                },
                'referenceType': {
                    'S': event['detail']['referenceType'],
                },
                'referenceName': {
                    'S': event['detail']['referenceName'],
                },
                'repositoryId': {
                    'S': event['detail']['repositoryId'],
                },
            }

        response = dynamodb.put_item(
            TableName=os.environ['TABLE_NAME'],
            ConditionExpression='attribute_not_exists(id)',
            Item=Item
        )
        print(response)
    except dynamodb.exceptions.ConditionalCheckFailedException as e:
        pass
    except Exception as e:
        print(e.message)


if __name__ == "__main__":
    with open('events/event.json') as json_file:
        event = json.loads(json_file.read())
    lambda_handler(event, '')
