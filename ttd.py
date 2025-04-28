import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, UTC
import pygsheets
from google.oauth2.service_account import Credentials

# Page config
st.set_page_config(page_title="Pick Claims Fact-Checking Task", layout="centered")

# Authenticate Google Sheets
@st.cache_resource
def get_gsheet_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gspread"],
        scopes=scopes
    )
    return pygsheets.authorize(custom_credentials=credentials)


# Create unique user session ID
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

# Header and user ID
st.title("Pick Claims to Fact-Check")
user_identifier = st.text_input("Please enter your Participant ID (required to proceed):")

st.markdown("""
In this task, you'll scan through a stream of posts and **select the ones you believe should be fact-checked**.
Use the tabs below to complete the task under two different views: a manual stream and an AI-ranked stream.
""")

# Load posts for Manual view
@st.cache_data
def load_manual_posts():
    return pd.read_csv("manual.csv")

# Load posts for Tool-Ranked view
@st.cache_data
def load_toolranked_posts():
    return pd.read_csv("tool.csv")


# Tab layout
tab1, tab2 = st.tabs(["Manual View", "Tool-Ranked View"])

# Function to render each condition
def render_tab(view_name, posts_df, sheet_name, timer_key):
    st.subheader(f"{view_name}")
    selections = []

    with st.form(f"form_{timer_key}"):
        for idx, row in posts_df.iterrows():
            st.markdown(f"**@{row['user_name']}**  |  **Likes:** {int(row['favorites']):,}  |  **Retweets:** {int(row['retweets']):,}  |  **Followers:** {int(row['user_followers']):,}  |  **Following:** {int(row['user_friends']):,}")

            st.markdown(f"**Post:** {row['text']}")
            selected = st.checkbox("Flag for Fact-Checking", key=f"select_{timer_key}_{row['post_id']}")
            st.divider()
            selections.append({
                "timestamp": datetime.now(UTC).isoformat(),
                "user_id": st.session_state.user_id,
                "participant_id": user_identifier,
                "post_id": row['post_id'],
                "rank": idx + 1,
                "selected": selected,
                "condition": view_name
            })

        submitted = st.form_submit_button(f"Submit {view_name} Flags")

        if submitted:
            if not user_identifier:
                st.warning("Please enter your Participant ID before submitting.")
            else:
                result_df = pd.DataFrame(selections)

                gc = get_gsheet_client()
                sheet = gc.open(sheet_name)
                wks = sheet.sheet1

                if not wks.get_all_records():
                    headers = ["timestamp", "user_id", "participant_id", "post_id", "rank", "selected", "condition"]
                    wks.update_row(1, headers)

                wks.append_table(result_df.values.tolist(), start='A2', end=None, dimension='ROWS', overwrite=False)
                st.success(f"Thank you! Your {view_name} flags have been submitted to Google Sheets.")


# Manual view: load and shuffle
with tab1:
    manual_df = load_manual_posts().sample(frac=1).reset_index(drop=True)
    render_tab("Manual View", manual_df, "TTD_Manual", "manual")

# Tool-ranked view: load and sort
with tab2:
    ranked_df = load_toolranked_posts().sort_values(by="model_score", ascending=False).reset_index(drop=True)
    render_tab("Tool-Ranked View", ranked_df, "TTD_ToolRanked", "tool")
