# pages/4_AI_Assistant.py
import os
import sqlite3
from pathlib import Path
import streamlit as st
import pandas as pd
import textwrap
import numpy as np
import datetime

# TRY TO ENABLE GOOGLE GENAI
USE_GENAI = False
try:
    # Enable GenAI only if the environment variable is present
    if os.environ.get("GENAI_API_KEY"):
        from google import genai  # Attempt import; failure sets USE_GENAI to False
        USE_GENAI = True
except Exception:
    # Any failure means the system falls back to offline local analysis
    USE_GENAI = False


# DATABASE HELPERS
# Path to the SQLite database that stores cyber incident records
DB_PATH = Path(__file__).resolve().parents[1] / "db" / "data.db"

def get_conn():
    # Create a SQLite connection (thread-safe for Streamlit)
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def get_incidents(limit=None) -> pd.DataFrame:
    # Query the incidents table and optionally limit results
    conn = get_conn()
    q = "SELECT rowid AS id, * FROM cyber_incidents"
    if limit:
        q += f" LIMIT {int(limit)}"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


# LOCAL OFFLINE ANALYZER (NO LLM)
def local_analyze_incident(row: pd.Series) -> str:
    # Build a markdown-formatted analysis using heuristic rules
    out = []
    out.append(f"### Incident {row.get('id')} — {row.get('title')}")
    out.append(f"- Severity: **{row.get('severity')}**")
    out.append(f"- Status: {row.get('status')}")
    out.append(f"- Reporter: {row.get('reporter')}")
    out.append("")

    # Use notes or fallback to description if missing
    notes = row.get("notes") or row.get("description") or "(no notes provided)"
    text = (str(row.get('title')) + " " + notes).lower()

    out.append("#### Summary")
    out.append(f"> {notes}")

    # Simple keyword-based root cause estimation
    rc = []
    if "phish" in text: rc.append("Likely phishing or social engineering attack.")
    if "malware" in text or "virus" in text: rc.append("Potential malware infection.")
    if "scan" in text: rc.append("Reconnaissance / port scanning detected.")
    if "password" in text: rc.append("Weak or compromised credentials involved.")
    if not rc:
        rc.append("Root cause unclear from available text; requires deeper investigation.")

    out.append("#### Root Cause (Heuristic)")
    for r in rc:
        out.append(f"- {r}")

    # Immediate action recommendations based on severity
    sev = str(row.get("severity")).lower()
    out.append("#### Immediate Actions")
    if "critical" in sev or "high" in sev:
        out.extend([
            "- Isolate affected system immediately.",
            "- Collect forensic logs and system image.",
            "- Reset credentials and enforce MFA.",
            "- Activate incident response escalation."
        ])
    else:
        out.extend([
            "- Contain affected device.",
            "- Review logs and recent activity.",
            "- Change credentials if needed."
        ])

    # General long-term security recommendations
    out.append("#### Long-term Prevention")
    out.extend([
        "- Improve user awareness training.",
        "- Harden endpoint configurations.",
        "- Enable better monitoring / alerting.",
        "- Patch vulnerabilities and update software."
    ])

    # Basic risk assessment logic
    out.append("#### Risk Assessment")
    if "critical" in sev:
        out.append("- High business impact likely.")
    else:
        out.append("- Impact appears moderate or low.")

    # Extra reminders for investigation hygiene
    out.append("#### Additional Notes")
    out.append("- Consider reviewing related IOCs and network logs.")
    out.append("- Ensure chain-of-custody for all evidence collected.")

    return "\n\n".join(out)

# OPTIONAL GENAI STREAMING LLM CALL
def stream_genai(prompt_text: str):
    """Yields partial LLM responses. Silent fallback handled by caller."""
    # Create GenAI client and stream the model response incrementally
    client = genai.Client(api_key=os.environ.get("GENAI_API_KEY"))
    stream = client.models.generate_content_stream(
        model="gemini-1.0-pro",
        contents=prompt_text
    )

    full = ""
    # Yield each chunk as it arrives so UI can update live
    for chunk in stream:
        text = getattr(chunk, "text", "")
        if text:
            full += text
            yield full


# UI
# Configure Streamlit layout
st.set_page_config(page_title="AI Incident Analyzer", layout="wide")
st.title("🚨 AI Incident Analyzer")

# Ensure user is logged in before accessing the tool
if not st.session_state.get("logged_in", False):
    st.info("Log in to access this tool.")
    st.stop()

# Load incidents
df = get_incidents(limit=500)
if df.empty:
    st.warning("No incidents found in database.")
    st.stop()

# Build selection labels (ID + title + severity)
labels = [f"{int(r['id'])}: {r.get('title')} — {r.get('severity')}" for _, r in df.iterrows()]
choice = st.selectbox("Select an incident", labels)

# Extract selected incident ID from label
selected_id = int(choice.split(":")[0])
row = df[df["id"] == selected_id].iloc[0]

# Display incident metadata
st.subheader("Incident Details")
st.write("**Title:**", row["title"])
st.write("**Severity:**", row["severity"])
st.write("**Status:**", row["status"])
st.write("**Reporter:**", row["reporter"])
st.write("**Notes:**")
st.write(row.get("notes") or row.get("description") or "(none)")

st.markdown("---")

# Display whether GenAI or the local analyzer will be used
mode = "GenAI" if USE_GENAI else "Local"
st.write(f"Analyzer mode: **{mode}**")

# Run analysis when button is clicked
if st.button("Analyze with AI"):
    with st.spinner("Analyzing incident..."):

        # Construct prompt for GenAI or fallback
        prompt = textwrap.dedent(f"""
        You are a senior cybersecurity analyst. Produce a structured analysis.
        Include: root cause, immediate actions, long-term prevention,
        risk assessment, evidence checklist, and executive summary.

        INCIDENT DATA:
        {row.to_dict()}
        """)

        if USE_GENAI:
            try:
                # Stream partial LLM responses to UI
                container = st.empty()
                for partial in stream_genai(prompt):
                    container.markdown(partial)
            except Exception:
                # Fail silently and use offline analyzer
                st.markdown(local_analyze_incident(row))
        else:
            # Offline deterministic analysis
            st.markdown(local_analyze_incident(row))

# Footer info about LLM usage
st.caption("Cloud LLM is used only if GENAI_API_KEY is set. Otherwise the offline local analyzer is used.")
