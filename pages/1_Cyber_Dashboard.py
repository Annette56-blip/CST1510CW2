# pages/1_Cyber_Dashboard.py
import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "data.db"
def get_conn():
    return sqlite3.connect(DB_PATH)

def safe_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        # fallback: HTML meta refresh (works as a last resort)
        st.markdown('<meta http-equiv="refresh" content="0">', unsafe_allow_html=True)
        st.stop()

# --- Access control ---
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("You must be logged in to view this page.")
    st.stop()

st.title("🔒 Cyber Dashboard")
conn = get_conn()
try:
    df = pd.read_sql("SELECT * FROM cyber_incidents", conn)
except Exception as e:
    st.error("Table cyber_incidents not found. Run your ingestion script!")
    conn.close()
    st.stop()
finally:
    conn.close()

# column mapping (case-insensitive)
cols = {c.lower(): c for c in df.columns}
id_col = cols.get("incident_id", cols.get("id", df.columns[0]))
ts_col = cols.get("timestamp")
severity_col = cols.get("severity")
category_col = cols.get("category")
status_col = cols.get("status")
# flexible description field
desc_col = cols.get("description", cols.get("notes", None))

# KPIs
k1, k2, k3 = st.columns(3)
k1.metric("Total incidents", len(df))
open_count = int(((df[status_col] == "open").sum()) if (status_col in df.columns) else 0)
k2.metric("Open incidents", open_count)
k3.metric("Most recent", str(df[ts_col].max()) if ts_col and ts_col in df.columns else "N/A")

st.divider()

# Severity distribution (interactive)
if severity_col and severity_col in df.columns:
    st.subheader("Severity Distribution (Interactive)")
    severity_counts = df[severity_col].fillna("UNKNOWN").value_counts()
    chart_df = pd.DataFrame({"Severity": severity_counts.index, "Count": severity_counts.values})
    st.bar_chart(chart_df.rename(columns={"Severity":"index"}).set_index("index"))
else:
    st.info("No 'severity' column found in cyber_incidents.")

st.subheader("Incidents (preview)")
st.dataframe(df, height=300)

st.divider()
st.subheader("Admin Tools")

if st.session_state.get("role") == "admin":
    if id_col in df.columns:
        pick = st.selectbox("Choose Incident ID", df[id_col].astype(str).tolist())
        chosen = df[df[id_col].astype(str) == str(pick)].iloc[0]
        st.write("Selected incident:", chosen.to_dict())

        # update status only if status column exists
        if status_col in df.columns:
            new_status = st.selectbox("New Status", ["open", "in_progress", "closed"])
            if st.button("Update Status"):
                conn = get_conn()
                conn.execute(f"UPDATE cyber_incidents SET {status_col}=? WHERE {id_col}=?", (new_status, pick))
                conn.commit(); conn.close()
                st.success("Incident updated.")
                safe_rerun()
        else:
            st.info("No 'status' column available to update.")

        if st.button("Delete Incident"):
            conn = get_conn()
            conn.execute(f"DELETE FROM cyber_incidents WHERE {id_col}=?", (pick,))
            conn.commit(); conn.close()
            st.success("Incident deleted.")
            safe_rerun()

        st.markdown("### Add New Incident")
        with st.form("add_incident", clear_on_submit=True):
            t_id = st.text_input("Incident ID (optional)")
            t_timestamp = st.text_input("Timestamp (ISO)")
            t_severity = st.selectbox("Severity", ["low","medium","high","critical"])
            t_category = st.text_input("Category")
            t_status = st.selectbox("Status", ["open","in_progress","closed"])
            t_description = st.text_area("Description")
            submitted = st.form_submit_button("Add Incident")
            if submitted:
                # Insert only columns that exist in table to avoid OperationalError
                to_insert = {}
                if "incident_id" in cols: to_insert["incident_id"] = (t_id or None)
                if "timestamp" in cols: to_insert["timestamp"] = (t_timestamp or None)
                if "severity" in cols: to_insert["severity"] = t_severity
                if "category" in cols: to_insert["category"] = t_category
                if "status" in cols: to_insert["status"] = t_status
                if "description" in cols: to_insert["description"] = t_description

                columns_sql = ", ".join(to_insert.keys())
                placeholders = ", ".join(["?"] * len(to_insert))
                values = list(to_insert.values())
                conn = get_conn()
                if columns_sql:
                    conn.execute(f"INSERT INTO cyber_incidents ({columns_sql}) VALUES ({placeholders})", values)
                    conn.commit()
                conn.close()
                st.success("Incident added.")
                safe_rerun()
    else:
        st.info("No incident ID column found; admin tools disabled.")
else:
    st.info("You are in read-only mode. Only admins can modify incidents.")
