# pages/1_Cyber_Dashboard.py
import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path

# ----------------------------
# DATABASE
# ----------------------------
DB_PATH = Path(__file__).resolve().parents[1] / "db" / "data.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def safe_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        st.markdown('<meta http-equiv="refresh" content="0">', unsafe_allow_html=True)
        st.stop()

# ----------------------------
# ACCESS CONTROL
# ----------------------------
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("You must be logged in to view this page.")
    st.stop()

# ----------------------------
# LOAD DATA
# ----------------------------
st.title("🔒 Cyber Dashboard")

conn = get_conn()
try:
    df = pd.read_sql("SELECT * FROM cyber_incidents", conn)
except Exception:
    st.error("Table cyber_incidents not found. Run the ingestion script.")
    conn.close()
    st.stop()
finally:
    conn.close()

if df.empty:
    st.warning("No cyber incidents available.")
    st.stop()

# ----------------------------
# COLUMN MAPPING (CASE-INSENSITIVE)
# ----------------------------
cols = {c.lower(): c for c in df.columns}

id_col       = cols.get("incident_id", cols.get("id"))
ts_col       = cols.get("timestamp")
severity_col = cols.get("severity")
category_col = cols.get("category")
status_col   = cols.get("status")
desc_col     = cols.get("description", cols.get("notes"))

# ----------------------------
# NORMALIZE TIMESTAMP (CRITICAL FIX)
# ----------------------------
if ts_col and ts_col in df.columns:
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=[ts_col])

# ----------------------------
# KPIs
# ----------------------------
k1, k2, k3 = st.columns(3)

k1.metric("Total incidents", len(df))

open_count = int((df[status_col] == "open").sum()) if status_col else 0
k2.metric("Open incidents", open_count)

if ts_col and not df.empty:
    most_recent = df[ts_col].max()
    k3.metric("Most recent", most_recent.strftime("%Y-%m-%d %H:%M"))
else:
    k3.metric("Most recent", "N/A")

st.divider()

# ----------------------------
# SEVERITY DISTRIBUTION
# ----------------------------
if severity_col:
    st.subheader("Severity Distribution (Interactive)")
    severity_counts = df[severity_col].fillna("UNKNOWN").value_counts()

    chart_df = pd.DataFrame({
        "Severity": severity_counts.index,
        "Count": severity_counts.values
    }).set_index("Severity")

    st.bar_chart(chart_df)
else:
    st.info("No severity column found.")

# ----------------------------
# INCIDENT TABLE
# ----------------------------
st.subheader("Incidents (Preview)")
st.dataframe(df, height=320)

st.divider()
st.subheader("Admin Tools")

# ----------------------------
# ADMIN CONTROLS
# ----------------------------
if st.session_state.get("role") == "admin" and id_col:

    ids = df[id_col].astype(str).tolist()
    pick = st.selectbox("Choose Incident ID", ids)

    selected_rows = df[df[id_col].astype(str) == str(pick)]
    if selected_rows.empty:
        st.error("Selected incident not found.")
        st.stop()

    chosen = selected_rows.iloc[0]
    st.write("Selected incident:", chosen.to_dict())

    # ---- UPDATE STATUS ----
    if status_col:
        new_status = st.selectbox(
            "New Status",
            ["open", "in_progress", "closed"],
            index=0
        )

        if st.button("Update Status"):
            conn = get_conn()
            conn.execute(
                f"UPDATE cyber_incidents SET {status_col}=? WHERE {id_col}=?",
                (new_status, pick),
            )
            conn.commit()
            conn.close()
            st.success("Incident status updated.")
            safe_rerun()

    # ---- DELETE INCIDENT ----
    if st.button("Delete Incident"):
        conn = get_conn()
        conn.execute(
            f"DELETE FROM cyber_incidents WHERE {id_col}=?",
            (pick,),
        )
        conn.commit()
        conn.close()
        st.success("Incident deleted.")
        safe_rerun()

    # ----------------------------
    # ADD NEW INCIDENT
    # ----------------------------
    st.markdown("### Add New Incident")

    with st.form("add_incident", clear_on_submit=True):
        t_id = st.text_input("Incident ID (optional)")
        t_timestamp = st.text_input("Timestamp (ISO format)")
        t_severity = st.selectbox("Severity", ["low", "medium", "high", "critical"])
        t_category = st.text_input("Category")
        t_status = st.selectbox("Status", ["open", "in_progress", "closed"])
        t_description = st.text_area("Description")

        submitted = st.form_submit_button("Add Incident")

        if submitted:
            to_insert = {}

            if "incident_id" in cols: to_insert["incident_id"] = t_id or None
            if "timestamp" in cols:   to_insert["timestamp"] = t_timestamp or None
            if "severity" in cols:    to_insert["severity"] = t_severity
            if "category" in cols:    to_insert["category"] = t_category
            if "status" in cols:      to_insert["status"] = t_status
            if "description" in cols: to_insert["description"] = t_description

            if to_insert:
                columns_sql = ", ".join(to_insert.keys())
                placeholders = ", ".join(["?"] * len(to_insert))

                conn = get_conn()
                conn.execute(
                    f"INSERT INTO cyber_incidents ({columns_sql}) VALUES ({placeholders})",
                    list(to_insert.values()),
                )
                conn.commit()
                conn.close()

                st.success("Incident added successfully.")
                safe_rerun()
            else:
                st.error("No valid columns found for insertion.")

else:
    st.info("Read-only mode. Admin access required to modify incidents.")
    