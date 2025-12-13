# pages/4_AI_Assistant.py
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd

# ----------------------------
# OPTIONAL GENAI SETUP
# ----------------------------
USE_GENAI = False
try:
    if os.environ.get("GENAI_API_KEY"):
        from google import genai
        from google.genai import types
        USE_GENAI = True
except Exception:
    USE_GENAI = False


# ----------------------------
# DATABASE LOADING
# ----------------------------
DB_PATH = Path(__file__).resolve().parents[1] / "db" / "data.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def load_incidents():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM cyber_incidents",
        conn,
        dtype={"incident_id": "string"}
    )
    conn.close()

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])

    return df


# ----------------------------
# LOCAL (OFFLINE) ANALYSIS
# ----------------------------
def local_analysis(question: str, df: pd.DataFrame) -> str:
    q = question.lower().strip()

    # Past X days
    if "past" in q and "days" in q:
        numbers = [int(s) for s in q.split() if s.isdigit()]
        days = numbers[0] if numbers else 2

        cutoff = datetime.utcnow() - timedelta(days=days)
        recent = df[df["timestamp"] >= cutoff]

        if recent.empty:
            return f"No cyber incidents recorded in the past {days} days."

        lines = [f"### Cyber Incidents in the Past {days} Days ({len(recent)} found)"]
        for _, r in recent.iterrows():
            lines.append(
                f"- **{r['timestamp']}** | "
                f"Severity: **{r.get('severity','N/A')}** | "
                f"Category: **{r.get('category','N/A')}**"
            )

        return "\n".join(lines)

    # Keyword search
    text_col = None
    for col in ["description", "notes"]:
        if col in df.columns:
            text_col = col
            break

    if text_col:
        keywords = ["phishing", "malware", "breach", "scan", "attack", "exploit"]
        for word in keywords:
            if word in q:
                hits = df[df[text_col].astype(str).str.contains(word, case=False, na=False)]
                if hits.empty:
                    return f"No incidents found related to **{word}**."
                return f"Found **{len(hits)}** incidents related to **{word}**."

    return (
        "I couldn’t confidently answer that.\n\n"
        "Try questions like:\n"
        "- *Show attacks in the past 3 days*\n"
        "- *Find phishing incidents*\n"
        "- *List high severity attacks*"
    )


# ----------------------------
# STREAMLIT UI (CHAT MODE)
# ----------------------------
st.set_page_config(page_title="AI Assistant", layout="wide")
st.title("🤖 AI Cyber Incident Assistant")

if not st.session_state.get("logged_in", False):
    st.warning("Please log in to use the assistant.")
    st.stop()

df = load_incidents()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    role = "assistant" if msg["role"] == "model" else msg["role"]
    with st.chat_message(role):
        st.markdown(msg["content"])

# Chat input
user_question = st.chat_input("Ask a question about cyber incidents...")

if user_question:
    # Save user message
    st.session_state.messages.append({
        "role": "user",
        "content": user_question
    })

    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):

            # ---------- CLOUD GENAI ----------
            if USE_GENAI:
                try:
                    client = genai.Client(api_key=os.environ["GENAI_API_KEY"])

                    prompt = f"""
You are a cybersecurity analyst.

QUESTION:
{user_question}

DATA SAMPLE:
{df.head(20).to_dict()}

Respond clearly, using the dataset where relevant.
"""

                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt
                    )

                    answer = response.text

                except Exception:
                    answer = local_analysis(user_question, df)

            # ---------- OFFLINE ----------
            else:
                answer = local_analysis(user_question, df)

            st.markdown(answer)

            # Save assistant reply
            st.session_state.messages.append({
                "role": "model",
                "content": answer
            })

st.caption("Cloud AI is used only if GENAI_API_KEY is configured. Otherwise offline analysis is applied.")
