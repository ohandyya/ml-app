import logging
import os
import uuid
import time
import datetime
import base64
from typing import Tuple

import pandas as pd
import numpy as np
import streamlit as st

import SessionState

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

PASSWORD = os.getenv("PASSWORD")
PROCESS_TIME = 10.0

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

# @st.cache(suppress_st_warning=True, max_entries=10)


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
    act_list, rec_act = recommend_activity(
        gender, past_activity, session_state.act_db)
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


def plan_daily_activity(session_state):
    st.subheader("Plan my daily activity")

    gender = st.selectbox(
        "Please select your gender",
        ("Male", "Female", "Choose to not disclose")
    )
    tstart = st.date_input("Start date")
    tend = st.date_input("End date")
    if tend <= tstart:
        st.write(
            "Please select a end date that is strickly larger than the start date")
    else:
        num_days = (tend - tstart).days
        req_id = str(uuid.uuid4())
        st.write(
            f"We are plaining {num_days} days of activity between {tstart} and {tend}. It may take some time.")
        st.write(f"Your requestID is: {req_id}")
        st.write("Please remember your requestID. You will need to use this requestID to download daily activity when it is ready.")
        submit_request(req_id, gender, tstart, tend, session_state)


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
        download_daily_activity(session_state)
    else:
        st.write("Not Implemented")


if __name__ == "__main__":
    if password == PASSWORD:
        logger.info("User entered the correct password")
        session_state = SessionState.get(
            act_db=INIT_ACTIVITY_DB,
            requests=dict()
        )
        main(session_state)
    else:
        logger.info(f"Wrong password entered: {password}")
        st.title("Please enter password!")
