import logging
import time
import boto3
import datetime
import json
import os
from typing import Optional, Tuple

import pandas as pd


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
REGION = 'us-east-1'
TABLE_NAME = "AppJobs"
INDEX_NAME = "jobToDo-requestedTs-index"
NEW_JOB_STR = "Y"

LAMBDA_FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME", "ml_app_lambda")
LAMBDA_QUALIFIER = os.getenv("LAMBDA_QUALIFIER", '$LATEST')
LAMBDA_REGION = os.getenv("LAMBDA_REGION", "us-east-1")

S3_BUCKET = "ml-app-2020"

SLEEP_SEC = 10


# Create DynamoDB client
client = boto3.client('dynamodb', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=LAMBDA_REGION)
s3_client = boto3.client('s3', region_name=REGION)


def update_new_job(item: dict) -> Tuple[dict, bool]:
    """Set the (jobId, requestedTs) to "working in progress"

    Args:
        item (dict):

    Returns:
        dict: updated item (if update is successful)
        bool: whether update is success or not

    """
    jobId = item.get("jobId", {}).get('S', "")
    requestedTs = item.get("requestedTs").get('N', "")
    try:
        logger.info(f"Update jobId={jobId}, requestedTs={requestedTs}")
        response = client.update_item(
            TableName=TABLE_NAME,
            Key={
                "jobId": {
                    "S": jobId,
                },
                "requestedTs": {
                    "N": requestedTs,
                },
            },
            UpdateExpression="REMOVE jobToDo SET jobStatus = :val",
            ExpressionAttributeValues={
                ':val': {
                    'S': "Working in progress"
                }
            },
        )
    except Exception as e:
        logger.error(
            f"Fail to update {TABLE_NAME}. jobId = {jobId}, "
            f"requestedTs={requestedTs}. Exception message: {e}"
        )
        return item, False

    # Check response code
    if response.get('ResponseMetadata', {}).get('HTTPStatusCode') != 200:
        logger.error(
            f"Receive non-200 http status code. Full response = {response}"
        )
        return item, False

    # Update item
    item['jobStatus'] = {'S': "Working in progress"}
    del item['jobToDo']
    return item, True


def get_one_new_job() -> Optional[dict]:
    """Get one new job from DynamoDB

    Returns:
        Optional[dict]:
            If there is new job, return a dict for the seleted new job
            If there is no new job, return None. For example,
                {'input': {'M': {'gender': {'S': 'Choose to not disclose'},
                'tend': {'S': '2020-06-01'},
                'tstart': {'S': '2020-02-01'}}},
                'jobStatus': {'S': 'New'},
                'jobId': {'S': '0e89023b-b2de-490d-8af2-e6b03acf516a'},
                'requestedTs': {'N': '1608910278'},
                'jobToDo': {'S': 'Y'}}
    """
    # No retry
    try:
        response = client.query(
            TableName=TABLE_NAME,
            IndexName=INDEX_NAME,
            KeyConditionExpression='jobToDo = :x',
            ExpressionAttributeValues={
                ':x': {
                    'S': NEW_JOB_STR,
                }
            },
        )
    except Exception as e:
        logger.error(f"Cannot query {TABLE_NAME}. Exception messae: {e}")
        return None

    # Check if thre is any new jobs
    if not response.get("Items"):
        logger.info(f"There is no new jobs in {TABLE_NAME}")
        item = None
    else:
        # There is at least one new items
        item = response.get("Items")[0]

        # Update item from DynamoDB
        jobId = item.get("jobId", {}).get('S', "")
        requestedTs = item.get("requestedTs").get('N', "")
        item, ok = update_new_job(item)
        if not ok:
            logger.error(
                f"Failed to update DynamoDB. jobId={jobId}, "
                f"requestedTs={requestedTs}"
            )
            item = None

    return item


def recommend_activity_lambda(
    gender: str,
    past_act: Optional[str] = "",
) -> Tuple[list, str]:
    """Get activity recommendation by invoking Lambda function

    Args:
        gender (str): [description]
        past_act (str): [description]

    Returns:
        Tuple[list, str]: [description]
    """
    payload = json.dumps(
        {
            "gender": gender,
            "past_act": past_act,
        }
    )
    # Invoke Lambda fucntion (no re-try for now)
    try:
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            Payload=payload,
            Qualifier=LAMBDA_QUALIFIER
        )

        res = json.loads(response['Payload'].read())
    except Exception as e:
        logger.error(
            f"Cannot invoke Lambda function: {LAMBDA_FUNCTION_NAME}. Return no recommendation."
            f"Error message: {e}"
        )
        return [], ""

    return res.get("activity_list", []), res.get("recommended_activity", "")


def write_df_to_s3_as_csv(df, key, bucket=S3_BUCKET) -> dict:
    """Write df to s3

    Args:
        df ([type]): [description]
        bucket ([type]): [description]
        key ([type]): [description]

    Returns:
        dict: response
    """
    try:
        response = s3_client.put_object(
            Body=df.to_csv(index=False).encode(),
            Bucket=bucket,
            Key=key
        )
    except Exception as e:
        logger.error(
            f"Failed to write df to S3. Bucket = {bucket}. key = {key}"
            f"Exception message: {e}"
        )
        return {}
    return response


def update_complete_job(item: dict, key: str) -> Tuple[dict, bool]:
    """Update item with completed job information

    Args:
        item (dict): [description]
        key (str): [description]

    Returns:
        dict: updated item
        bool: whether the update is success or not

    """
    jobId = item.get("jobId", {}).get('S', "")
    requestedTs = item.get("requestedTs").get('N', "")
    try:
        logger.info(
            f"Job complete update: jobId={jobId}, requestedTs={requestedTs}")
        _ = client.update_item(
            TableName=TABLE_NAME,
            Key={
                "jobId": {
                    "S": jobId,
                },
                "requestedTs": {
                    "N": requestedTs,
                },
            },
            UpdateExpression="SET jobStatus = :val, outData = :out",
            ExpressionAttributeValues={
                ':val': {
                    'S': "Done"
                },
                ':out': {
                    'M': {
                        "Bucket": {
                            'S': S3_BUCKET,
                        },
                        "Key": {
                            'S': key,
                        }
                    }
                }
            },
        )
    except Exception as e:
        logger.error(
            f"Job complete update fail: {TABLE_NAME}, jobId = {jobId}, "
            f"requestedTs={requestedTs}. Exception message: {e}"
        )
        return item, False

    # Update item
    item["jobStatus"] = "Done"
    item["outData"] = {
        'M': {
            "Bucket": {
                'S': S3_BUCKET,
            },
            "Key": {
                'S': key,
            }
        }
    }
    return item, True


def run_task(item: dict) -> dict:
    """Run task defined by item

    Args:
        item (dict): [description]

    Returns:
        dict: updated item
    """
    # Get jobId
    jobId = item.get("jobId", {}).get('S', "")

    # Get gender
    gender = item.get("input", {}).get('M', {}).get('gender', {}).get('S')
    try:
        tstart = datetime.datetime.strptime(
            item.get("input", {}).get('M', {}).get('tstart', {}).get('S', ""),
            '%Y-%m-%d'
        ).date()

        tend = datetime.datetime.strptime(
            item.get("input", {}).get('M', {}).get('tend', {}).get('S', ""),
            '%Y-%m-%d'
        ).date()
    except Exception as e:
        logger.error(
            f"Failed to convert tstart and/or tend. item: {item}. "
            f"Cannot process this task. Exception message: {e}"
        )
        return item

    # Create output df
    data = {
        "date": [],
        "activity": [],
    }
    day = tstart
    while day < tend:
        _, rec_act = recommend_activity_lambda(gender)
        data['date'].append(day)
        data["activity"].append(rec_act)
        day += datetime.timedelta(days=1)
    df = pd.DataFrame(data)

    # Write df to S3
    key = f"daily_activity/{jobId}.csv"
    _ = write_df_to_s3_as_csv(df, key)

    # Update item
    item, ok = update_complete_job(item, key)
    return item


def main():
    item = get_one_new_job()
    while item:
        jobId = item.get("jobId", {}).get('S', "")
        logger.info(f"Processing new job: {jobId}")
        _ = run_task(item)
        logger.info(f"Complete job: {jobId}")
        if SLEEP_SEC:
            logger.info(f"Sleep for {SLEEP_SEC} seconds")
            time.sleep(SLEEP_SEC)
        item = get_one_new_job()


if __name__ == "__main__":
    logger.info("Starting backend task...")
    main()
    logger.info("Ending backend task...")
