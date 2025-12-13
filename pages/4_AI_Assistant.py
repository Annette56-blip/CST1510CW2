# pages/4_AI_Assistant.py
import os
import sqlite3
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ----------------------------
# OPTIONAL GENAI SETUP
# ----------------------------
USE_GENAI = False
try:
    if os.environ.get("GENAI_API_KEY"):
        from google import genai
        USE_GENAI = True
except:
    USE_GENAI = False


# ----------------------------
# DATABASE LOADING
# ----------------------------
DB_PATH = Path(__file__).resolve().parents[1] / "db" / "data.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)
    x
def load_incidents():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM cyber_incidents",
        conn,
        dtype={"incident_id": "string"}
)


    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])

    return df

# local_analysis

def local_analysis(question: str, df: pd.DataFrame):
    q = question.lower().strip()

    # 1 — PAST X DAYS DETECTION
    if "past" in q and "days" in q:
        numbers = [int(s) for s in q.split() if s.isdigit()]
        num = numbers[0] if numbers else 2

        cutoff = datetime.utcnow() - timedelta(days=num)
        recent = df[df["timestamp"] >= cutoff]

        if recent.empty:
            return f"### No cyber attacks recorded in the past {num} day(s)."

        out = [f"### Cyber Attacks in the Past {num} Days ({len(recent)} found)"]
        for _, r in recent.iterrows():
            out.append(
                f"- **{r['timestamp']}** | Severity: **{r['severity']}** | "
                f"Category: **{r['category']}** | Description: {r.get('description', '(no description)')}"
            )

        return "\n".join(out)

    # 2 — KEYWORD SEARCH
    keywords = ["phishing", "malware", "breach", "scan", "attack", "exploit"]

    # Always determine searchable column
    if "description" in df.columns:
        text_col = "description"
    elif "notes" in df.columns:
        text_col = "notes"
    else:
        text_col = None

    for word in keywords:
        if word in q:
            # If no column to search, return empty immediately
            if not text_col:
                return f"### No searchable text column found to look for **{word}**."

            hits = df[
                df[text_col].astype(str).str.contains(word, case=False, na=False)
            ]

            if hits.empty:
                return f"### No incidents found related to **{word}**."

            out = [f"### Incidents related to '{word}' ({len(hits)} found)"]
            for _, r in hits.iterrows():
                out.append(
                    f"- {r['timestamp']} | {r['severity']} | {r.get(text_col, '(no details)')}"
                )

            return "\n".join(out)

    # 3 — FALLBACK
    return f"""
### I understood your question as:

> **{question}**

But I need more detail.  
Try something like:

- “show all attacks in the past 3 days”
- “find phishing incidents”
- “list high severity incidents”
"""



# ----------------------------
# GENAI CLOUD ANALYSIS
# ----------------------------
def genai_answer(question: str, df: pd.DataFrame):
    client = genai.Client(api_key=os.environ["GENAI_API_KEY"])

    prompt = f"""
You are a cybersecurity analyst. Use the dataset below to answer:

QUESTION:
{question}

DATA SAMPLE:
{df.head(15).to_dict()}

Give:
- direct answer
- list of matching incidents
- severity interpretation
- risk implications
- recommendations
"""

    ### >>> CHANGE MODEL HERE <<<
    model_name = "gemini-2.0-flash"

    stream = client.models.generate_content_stream(
        model=model_name,
        contents=prompt
    )

    full = ""
    for chunk in stream:
        text = getattr(chunk, "text", "")
        if text:
            full += text
            yield full


# ----------------------------
# STREAMLIT UI
# ----------------------------
st.set_page_config(page_title="AI Assistant", layout="wide")
st.title("🤖 AI Cyber Incident Assistant")

if not st.session_state.get("logged_in", False):
    st.warning("Please log in to use the assistant.")
    st.stop()

df = load_incidents()

st.write("### Ask any question about cyber attacks:")
question = st.text_input("Example: Show attacks in the past 2 days")

if st.button("Analyze"):
    if not question.strip():
        st.warning("Type something first.")
        st.stop()

    with st.spinner("Analyzing..."):

        if USE_GENAI:
            try:
                container = st.empty()
                for partial in genai_answer(question, df):
                    container.markdown(partial)
            except Exception as e:
                st.error("Cloud AI failed. Using offline mode.")
                st.markdown(local_analysis(question, df))
        else:
            st.markdown(local_analysis(question, df))

st.caption("Cloud LLM used ONLY if GENAI_API_KEY is set. Otherwise offline mode is used.")
