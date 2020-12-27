import logging
import os
import uuid
import time
import datetime
import base64
import boto3
import json
from typing import Tuple, Any, Optional

import pandas as pd
import numpy as np
import streamlit as st

import SessionState

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

PASSWORD = os.getenv("PASSWORD")
PROCESS_TIME = 10.0
LAMBDA_FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME", "ml_app_lambda")
LAMBDA_QUALIFIER = os.getenv("LAMBDA_QUALIFIER", '$LATEST')
LAMBDA_REGION = os.getenv("LAMBDA_REGION", "us-east-1")

REGION = 'us-east-1'
TABLE_NAME = "AppJobs"
INDEX_NAME = "jobToDo-requestedTs-index"


password = st.sidebar.text_input("Enter a password", value="", type="password")
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


def get_table_download_link(df):
    """Generates a link allowing the data in a given panda dataframe to be downloaded
    in:  dataframe
    out: href string
    """
    csv = df.to_csv(index=False)
    # some strings <-> bytes conversions necessary here
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}">Download csv file</a>'
    return href


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


def recommend_activity_lambda(
    gender: str,
    past_act: str,
    lambda_client: Any,
) -> Tuple[list, str]:
    """Get activity recommendation by invoking Lambda function

    Args:
        gender (str): [description]
        past_act (str): [description]
        lambda_client (Any): Lambda client

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


def activity_now(session_state):
    st.subheader('What activity shall I do today?')
    gender = st.selectbox(
        "Please select your gender",
        ("Male", "Female", "Choose to not disclose")
    )
    past_activity = st.text_input(
        "What activity you had done before?",
        value="",
    )
    # Invoke local recommend_activity
    # act_list, rec_act = recommend_activity(
    #    gender, past_activity, session_state.act_db)

    # Invoke Lambda recommend_activity
    act_list, rec_act = recommend_activity_lambda(
        gender,
        past_activity,
        session_state.lambda_client,
    )
    if not rec_act:
        st.write("Something is wrong with the system. No recommendation available.")
    else:
        st.write(
            f"Based on your input, among all possible activies {act_list}, my recommendation is... ")
        st.markdown(f"**{rec_act}**")


def submit_request(requestID: str, gender: str, tstart: datetime.date, tend: datetime.date, session_state):
    submission_time = time.time()
    logger.info(f"Submite requestID: {requestID} at {submission_time}")
    session_state.requests[requestID] = {
        "gender": gender,
        "tstart": tstart,
        "tend": tend,
        "submission_time": submission_time
    }


def is_any_running_backend_ecs_task(ecs_client) -> bool:
    """Check if there is any ECS backend task with desiredStatus = "RUNNING"

    Args:
        ecs_client ([type]): [description]

    Returns:
        bool:
            True: there is at least one task with desiredStatus = "RUNNING"
            False: otherwise
    """
    try:
        response = ecs_client.list_tasks(
            cluster="ml-app-frontend",
            family="ml_app_backend",
            desiredStatus="RUNNING",
        )
    except Exception as e:
        logger.error(
            f"Failed to call ecs_client.list_tasks(...). Exception message: {e}")
        return False
    else:
        num_tasks = len(response.get('taskArns', []))
        logger.info(
            f"There are {num_tasks} ml_app_backend tasks with desiredStatus = 'RUNNING'")
        return num_tasks > 0


def run_backend_ecs_tasks(ecs_client):
    """Run backend ECS tasks

    Args:
        ecs_client ([type]): [description]
    """
    try:
        logger.info("Run ml_app_backend:1 task")
        _ = ecs_client.run_task(
            cluster="arn:aws:ecs:us-east-1:381982364978:cluster/ml-app-frontend",
            count=1,
            launchType="FARGATE",
            taskDefinition="ml_app_backend:1",
            networkConfiguration={
                "awsvpcConfiguration": {
                    'subnets': ["subnet-c66e8999"],
                    'securityGroups': ["sg-09af5a1923947eac8"],
                    'assignPublicIp': 'ENABLED'
                }
            }
        )
    except Exception as e:
        logger.error(
            f"Failed to run ml_app_backend:1 task. Exception message: {e}")


def submit_request_dynamodb(
    requestID: str,
    gender: str,
    tstart: datetime.date,
    tend: datetime.date,
    dynamodb_client: Any,
) -> bool:
    submission_time = time.time()
    logger.info(f"Submite requestID: {requestID} at {submission_time}")
    try:
        response = dynamodb_client.put_item(
            TableName=TABLE_NAME,
            Item={
                'jobId': {
                    "S": requestID,
                },
                "requestedTs": {
                    "N": str(time.time()),
                },
                "jobToDo": {
                    "S": 'Y',
                },
                "jobStatus": {
                    "S": "New",
                },
                "input": {
                    "M": {
                        "gender": {
                            "S": gender,
                        },
                        "tstart": {
                            "S": tstart.strftime("%Y-%m-%d"),
                        },
                        "tend": {
                            "S": tend.strftime("%Y-%m-%d"),
                        },
                    }
                }
            },
            ReturnValues="ALL_OLD",
        )
    except Exception as e:
        logger.error(
            f"Fail to submit new job to {TABLE_NAME}. jobId = {requestID}. "
            f"Exception message: {e}"
        )
        return False
    else:
        if response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 200:
            logger.error(
                f"Put new item get non-200 return code. full respose = {response}")
            return False
    return True


def plan_daily_activity(session_state):
    st.subheader("Plan my daily activity")

    gender = st.selectbox(
        "Please select your gender",
        ("Male", "Female", "Choose to not disclose")
    )
    tstart = st.date_input("Start date")
    tend = st.date_input("End date")
    if st.button("Submit job"):
        if tend <= tstart:
            st.write(
                "Please select a end date that is strickly larger than the start date")
        else:
            num_days = (tend - tstart).days
            req_id = str(uuid.uuid4())
            st.write(
                f"We are plaining {num_days} days of activity between {tstart} and {tend}. It may take some time.")
            st.write(f"Your requestID is: {req_id}")
            st.write(
                "Please remember your requestID. You will need to use this requestID to download daily activity when it is ready.")
            #submit_request(req_id, gender, tstart, tend, session_state)
            ok = submit_request_dynamodb(req_id, gender, tstart,
                                         tend, session_state.dynamodb_client)
            if ok and not is_any_running_backend_ecs_task(session_state.ecs_client):
                run_backend_ecs_tasks(session_state.ecs_client)


def get_activity(req_id: str, gender: str, tstart: datetime.date, tend: datetime.date, session_state) -> pd.DataFrame:
    """[summary]

    Args:
        req_id (str): [description]
        gender (str): [description]
        tstart (datetime.date): [description]
        tend (datetime.date): [description]

    Returns:
        pd.DataFrame: [description]
    """
    data = {
        "date": [],
        "activity": [],
    }
    day = tstart
    while day < tend:
        _, rec_act = recommend_activity(gender, "", session_state.act_db)
        data["date"].append(day)
        data["activity"].append(rec_act)
        day += datetime.timedelta(days=1)

    df = pd.DataFrame(data)
    return df


def download_job(jobId: str, dynamodb_client: Any) -> Optional[dict]:
    """Download job from DynamoDB

    Args:
        jobId (str): [description]
        dynamodb_client (Any): [description]

    Returns:
        Optional[dict]: [description]
            None means there is some error
            empty dict means there is no item for this jobId
    """
    try:
        response = dynamodb_client.query(
            TableName=TABLE_NAME,
            KeyConditionExpression='jobId = :x',
            ExpressionAttributeValues={
                ':x': {
                    'S': jobId,
                }
            },
        )
    except Exception as e:
        logger.error(
            f"Fail to query {TABLE_NAME}. jobId = {jobId}. Exception message: {e}")
        return None
    else:
        cnt = len(response.get("Items", []))
        if cnt == 0:
            logger.warning(f"There are no job for jobId = {jobId}")
            return {}
        elif cnt > 1:
            logger.error(
                f"Found {cnt} jobs for jobId = {jobId}. This means DynamoDB is corroupted. Fix it now.")
            return None
        else:
            # cnt == 1
            return response.get("Items")[0]


def download_daily_activity(session_state):
    st.subheader("Download daily activity")

    req_id = st.text_input("Request ID")

    if req_id not in session_state.requests:
        st.write(
            f"Cannot find {req_id}. Please double check the request ID you provide.")
    else:
        if session_state.requests[req_id]["submission_time"] < time.time() - PROCESS_TIME:
            st.write(f"{req_id} ready for download")
            df = get_activity(
                req_id,
                session_state.requests[req_id]["gender"],
                session_state.requests[req_id]["tstart"],
                session_state.requests[req_id]["tend"],
                session_state,
            )
            st.markdown(get_table_download_link(df), unsafe_allow_html=True)

        else:
            st.write(f"{req_id} is not ready yet. Please try again latter.")


def download_csv_from_s3(bucket: str, key: str, s3_client: Any) -> Optional[pd.DataFrame]:
    """Download CSV from s3

    Args:
        key (str): [description]
        s3_client (Any): [description]

    Returns:
        pd.DataFrame: [description]
    """
    try:
        response = s3_client.get_object(
            Bucket=bucket,
            Key=key
        )
        df = pd.read_csv(response["Body"])
    except Exception as e:
        logger.error(
            f"Failed to download S3 file as pd.Dataframe. Bucket = {bucket}. Key = {key}. Exception message: {e}")
        return None
    else:
        return df


def download_daily_activity_dynamodb(session_state):
    st.subheader("Download daily activity")

    req_id = st.text_input("Request ID")

    if req_id:
        item = download_job(req_id, session_state.dynamodb_client)

        if item is None:
            st.write(
                "Something is wrong with the system. Please inform the maintainer."
                f" jobId = {req_id}"
            )
        elif item == dict():
            st.write(
                f"Cannot find job for requeset id = {req_id}. Please make sure you have provided the correct request id.")
        else:
            st.write("Found the requested job.")
            jobStatus = item.get('jobStatus', {}).get('S', 'UNKNOWN')
            st.write(
                f"The current job status is: '{jobStatus}' ")
            if jobStatus == 'Done':
                bucket = item.get('outData', {}).get(
                    'M', {}).get("Bucket", {}).get('S', "")
                key = item.get('outData', {}).get(
                    'M', {}).get("Key", {}).get('S', "")
                if bucket and key:
                    df = download_csv_from_s3(
                        bucket, key, session_state.s3_client)
                    if isinstance(df, pd.DataFrame):
                        st.markdown(get_table_download_link(
                            df), unsafe_allow_html=True)
                    else:
                        st.write(
                            "Failed to download file. Please inform the maintainer"
                            f"bucket={bucket}. key={key}"
                        )
                else:
                    st.write(
                        f"Something is wrong; either bucket or key cannot be "
                        f"found. Please inform the maintainer. bucket={bucket}."
                        f" key={key}"
                    )


def main(session_state):
    st.title('Activity Recommender')

    task = st.sidebar.selectbox(
        "Select an analysis job",
        ("What activity to do right now?",
         "Plan my daily activity", "Download my daily activity")
    )

    if task == "What activity to do right now?":
        activity_now(session_state)
    elif task == "Plan my daily activity":
        plan_daily_activity(session_state)
    elif task == "Download my daily activity":
        # download_daily_activity(session_state)
        download_daily_activity_dynamodb(session_state)
    else:
        st.write("Not Implemented")


if __name__ == "__main__":
    if password == PASSWORD:
        logger.info("User entered the correct password")
        session_state = SessionState.get(
            act_db=INIT_ACTIVITY_DB,
            requests=dict(),
        )
        session_state.lambda_client = boto3.client(
            'lambda', region_name=LAMBDA_REGION)
        session_state.dynamodb_client = boto3.client(
            'dynamodb', region_name=REGION)
        session_state.s3_client = boto3.client('s3', region_name=REGION)
        session_state.ecs_client = boto3.client('ecs', region_name=REGION)

        main(session_state)
    else:
        logger.info(f"Wrong password entered: {password}")
        st.title("Please enter password!")
