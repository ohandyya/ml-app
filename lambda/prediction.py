from typing import Tuple, Dict
import logging

import numpy as np
import boto3

# Constants
REGION = "us-east-1"
TABLE_NAME = "ActivityCnt"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

client = boto3.client('dynamodb', region_name=REGION)


INIT_ACTIVITY_DB = {
    "male": {
        "basketball": 1,
        "baseball": 1,
        "swimming": 1,
    },
    "female": {
        "shopping": 1,
        "swimming": 1,
    },
}


def get_act_cnt_from_dynamodb(gender: str) -> Dict[str, int]:
    """Get per-gender activity count from DyanmoDB

    Args:
        gender (str): [description]

    Returns:
        Dict[str, int]: [description]
    """
    # Query DybamoDB
    try:
        response = client.query(
            TableName=TABLE_NAME,
            KeyConditionExpression='gender = :genderVal',
            ExpressionAttributeValues={
                ':genderVal': {
                    'S': gender,
                }
            },
        )
    except Exception as e:
        logger.error(
            f"Failed to query DynamoDB: {TABLE_NAME}. Error message: {e}. "
            "Return empty dictionary."
        )
        return dict()

    # Create final dict
    res = dict()
    for item in response.get('Items', []):
        activity = item.get("activity", {}).get("S", "")
        cnt = int(item.get("cnt", {}).get("N", '0'))
        res[activity] = cnt

    logger.info(f"For {gender}, the activity count is: {res}")
    return res


def update_dynamodb(gender: str, activity: str):
    """Update dynamoDB

    Args:
        gender (str): [description]
        activity (str): [description]
    """
    try:
        response = client.update_item(
            TableName=TABLE_NAME,
            Key={
                "gender": {
                    "S": gender,
                },
                "activity": {
                    "S": activity,
                },
            },
            UpdateExpression="ADD cnt :x",
            ExpressionAttributeValues={
                ':x': {
                    'N': '1',
                },
            }
        )
        logger.info(f"Update response: {response}")
    except Exception as e:
        logger.error(f"Failed to update DynamoDB. Exception message: {e}")


def recommend_activity_dynamodb(gender: str, past_act: str) -> Tuple[list, str]:
    """Recommend activity based on gender and past_act from DynamoDB

    Args:
        gender (str): [description]
        past_act (str): [description]

    Returns:
        str: [description]
    """
    all_gen = {'male', 'female'}
    gender = gender.lower()

    # Update DynamoDB
    if gender in all_gen and past_act:
        update_dynamodb(gender, past_act)

    # Create activity_db
    activity_db = dict()
    if gender in all_gen:
        activity_db[gender] = get_act_cnt_from_dynamodb(gender)
    else:
        for gen in all_gen:
            activity_db[gen] = get_act_cnt_from_dynamodb(gen)

    # Get possible activities and total count
    act_list = []
    prob_list = []
    for gender_tmp, act_cnt_map in activity_db.items():
        for act, cnt in act_cnt_map.items():
            act_list.append(act)
            prob_list.append(cnt)
    total_cnt = sum(prob_list)

    # Handle no activity case
    if total_cnt == 0:
        logger.warning(
            f"No activity found for gender = {gender}"
            "Return [], ''"
        )
        return [], ""

    prob_list = [float(v) / total_cnt for v in prob_list]

    logger.info(f"act_list = {act_list}, prob_list = {prob_list}")

    # Select a activity
    rng = np.random.default_rng()
    act = rng.choice(act_list, size=1, replace=False, p=prob_list)[0]
    return act_list, act


def recommend_activity(gender: str, past_act: str, activity_db: dict) -> Tuple[list, str]:
    """Recommend activity based on gender and past_act

    Args:
        gender (str): [description]
        past_act (str): [description]
        activity_db (dict): Activity DB

    Returns:
        str: [description]
    """
    all_gen = set(activity_db.keys())
    gender = gender.lower()
    if past_act:
        # Update activity_db
        if gender in activity_db:
            if past_act not in activity_db[gender]:
                activity_db[gender][past_act] = 1
            else:
                activity_db[gender][past_act] += 1
            logger.info(activity_db)

    # Get possible activities and total count
    act_list = []
    prob_list = []
    for gender_tmp, act_cnt_map in activity_db.items():
        if gender == gender_tmp or gender not in all_gen:
            for act, cnt in act_cnt_map.items():
                act_list.append(act)
                prob_list.append(cnt)
    total_cnt = sum(prob_list)
    prob_list = [float(v) / total_cnt for v in prob_list]

    logger.info(f"act_list = {act_list}, prob_list = {prob_list}")

    # Select a activity
    rng = np.random.default_rng()
    act = rng.choice(act_list, size=1, replace=False, p=prob_list)[0]
    return act_list, act


def handler(event, context):
    gender = event.get("gender", 'n/a')
    past_act = event.get("past_act", "")
    logger.info(
        f"Get request with gender = {gender} and past_act = {past_act}")
    #act_list, act = recommend_activity(gender, past_act, INIT_ACTIVITY_DB)
    act_list, act = recommend_activity_dynamodb(gender, past_act)
    return {"activity_list": act_list, "recommended_activity": act}
