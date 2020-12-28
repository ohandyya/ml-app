import streamlit as st
import base64
# To make things easier later, we're also importing numpy and pandas for
# working with sample data.
import datetime
import numpy as np
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

VALID_PASSWORD = ["password"]

password = st.sidebar.text_input("Enter a password", value="", type="password")


def my_long_func():
    time.sleep(5)
    return 10


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


@st.cache(suppress_st_warning=True)  # 👈 Changed this
def expensive_computation(a, b):
    # 👇 Added this
    st.write("Cache miss: expensive_computation(", a, ",", b, ") ran")
    time.sleep(2)  # This makes the function take 2s to run
    return a * b


def main():
    st.title('My first app')

    st.header("This is a header")
    st.subheader("this is a subheader")
    st.text("this is my test")

    code = '''
    def myf(variable):
        return variable
    '''
    st.code(code, language="python")

    st.header("This section is about data frame")
    st.write("Here's our first attempt at using data to create a table:")
    df = pd.DataFrame({
        'first column': [1, 2, 3, 4],
        'second column': [10, 20, 30, 40]
    }, index=['a', 'b', 'c', 'd'])
    df.index.name = "my shortcut"

    st.write(df)
    st.dataframe(df)
    st.table(df)

    chart_data = pd.DataFrame(
        np.random.randn(20, 3),
        columns=['a', 'b', 'c'])

    st.line_chart(chart_data)

    map_data = pd.DataFrame(
        0.1 * np.random.randn(1000, 2) / [50, 50] + [37.76, -122.4],
        columns=['lat', 'lon'])
    st.dataframe(map_data)
    st.map(map_data)

    if st.checkbox('Show dataframe'):
        chart_data = pd.DataFrame(
            np.random.randn(20, 3),
            columns=['a', 'b', 'c'])

        st.line_chart(chart_data)

    option = st.selectbox("What sports doe you link?", [
        'Basketball', "Baseball"])
    st.write("You like ", option)

    chart_data = pd.DataFrame(
        np.random.randn(20, 3),
        columns=['a', 'b', 'c'])

    st.sidebar.line_chart(chart_data)

    left_column, right_column = st.beta_columns(2)

    pressed = left_column.button('Press me?')
    if pressed:
        right_column.write("Woohoo!")

    expander = st.beta_expander("FAQ")
    expander.write(
        "Here you could put in some really, really long explanations...")

    st.write('Starting a long computation...')

    # Add a placeholder
    latest_iteration = st.empty()
    bar = st.progress(0)

    for i in range(100):
        # Update the progress bar with each iteration.
        latest_iteration.text(f'Iteration {i+1}')
        bar.progress(i + 1)
        time.sleep(0.001)

    st.write('...and now we\'re done!')

    if st.button("Run my function"):
        st.write("Running.....")
        val = my_long_func()
        st.write("Value = ", val)

    genre = st.radio("What's your favorite movie genre",
                     ('Comedy', 'Drama', 'Documentary'))
    if genre == "Comedy":
        st.write("You select Comedy")
    else:
        st.write("You did not like Comedy???")

    options = st.multiselect('What are your favorite colors', [
                             'Green', 'Yellow', 'Red', 'Blue'])
    st.write("You select: ", options)

    age = st.slider('How old are you?', 0, 130, 25)
    st.write("I'm ", age, 'years old')

    title = st.text_input('Movie title', 'Life of Brian')
    st.write('The current movie title is', title)

    txt = st.text_area('Text to analyze')
    st.write(txt)

    bd = st.date_input("When is your birthday?")
    st.write("Your birthday is :", bd)

    t = st.time_input('Set an alarm for', datetime.time(8, 42))
    st.write('Alarm is set for', t)

    uploaded_file = st.file_uploader("Choose a file")
    if uploaded_file:
        dataframe = pd.read_csv(uploaded_file)
        st.write(dataframe)

    color = st.color_picker('Pick A Color', '#00f900')
    st.write('The current color is', color)

    st.markdown(get_table_download_link(df), unsafe_allow_html=True)

    num1 = st.number_input("Insert number 1", value=0.0)
    num2 = st.number_input("Insert number 2", value=0.0)
    res = expensive_computation(num1, num2)
    st.write(f"{num1} x {num2} equals ", res)


if __name__ == "__main__":
    if password in VALID_PASSWORD:
        logger.info("User put correct password")
        main()
    else:
        st.title("Wrong password entered")
        logger.info("User put wrong password")
#    st.stop()
