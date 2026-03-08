"""
CRLA Dashboard — Router

Entry point for the multi-page Streamlit dashboard.

Usage:
    streamlit run dashboard/app.py --server.port 8050
"""

import streamlit as st

st.set_page_config(
    page_title="CRLA Dashboard",
    page_icon="\U0001F4DA",
    layout="wide",
)

pages = [
    st.Page("pages/school_view.py", title="School View", icon="\U0001F3EB"),
    st.Page("pages/ranked_view.py", title="Ranked View", icon="\U0001F3C6"),
]

nav = st.navigation(pages)
nav.run()
