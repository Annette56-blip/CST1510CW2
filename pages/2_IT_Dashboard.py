# pages/2_IT_Dashboard.py
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
        st.markdown('<meta http-equiv="refresh" content="0">', unsafe_allow_html=True)
        st.stop()

# ----- Access control -----
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("You must be logged in to view this page.")
    st.stop()

st.title("🛠 IT Operations Dashboard")
conn = get_conn()
try:
    df = pd.read_sql("SELECT * FROM it_tickets", conn)
except Exception:
    st.error("Table it_tickets not found. Run your ingestion script!")
    conn.close()
    st.stop()
finally:
    conn.close()

cols = {c.lower(): c for c in df.columns}
id_col = cols.get("ticket_id", cols.get("id", df.columns[0]))
priority_col = cols.get("priority")
status_col = cols.get("status")
assign_col = cols.get("assigned_to", cols.get("assignee"))
res_col = cols.get("resolution_time_hours")
created_col = cols.get("created_at")

# KPIs
k1, k2, k3 = st.columns(3)
k1.metric("Total Tickets", len(df))
k2.metric("Open Tickets", int(((df[status_col] == "open").sum()) if (status_col in df.columns) else 0))
if res_col and res_col in df.columns:
    avg_res = df[res_col].dropna()
    k3.metric("Avg Resolution (hrs)", f"{avg_res.mean():.1f}" if not avg_res.empty else "N/A")
else:
    k3.metric("Avg Resolution (hrs)", "N/A")

st.divider()
col1, col2 = st.columns((2,3))

with col1:
    st.subheader("Priority Distribution")
    if priority_col and priority_col in df.columns:
        pri_counts = df[priority_col].fillna("UNKNOWN").value_counts()
        chart_df = pd.DataFrame({"Priority": pri_counts.index, "Count": pri_counts.values})
        st.bar_chart(chart_df.rename(columns={"Priority":"index"}).set_index("index"))
    else:
        st.info("No 'priority' column found.")

with col2:
    st.subheader("Status Breakdown")
    if status_col and status_col in df.columns:
        stat_counts = df[status_col].fillna("UNKNOWN").value_counts()
        chart_df2 = pd.DataFrame({"Status": stat_counts.index, "Count": stat_counts.values})
        st.bar_chart(chart_df2.rename(columns={"Status":"index"}).set_index("index"))
    else:
        st.info("No 'status' column found.")

st.divider()
st.subheader("Tickets Table")
st.dataframe(df, height=300)

st.subheader("Update / Delete Ticket")
if st.session_state.get("role") == "admin":
    if not df.empty:
        pick = st.selectbox("Choose Ticket ID:", df[id_col].astype(str).tolist())
        chosen = df[df[id_col].astype(str) == str(pick)].iloc[0]
        st.write("Selected:", chosen.to_dict())

        if status_col in df.columns:
            new_status = st.selectbox("New Status:", ["open", "in_progress", "closed"], index=0)
            if st.button("Update Status"):
                conn = get_conn()
                conn.execute(f"UPDATE it_tickets SET {status_col}=? WHERE {id_col}=?", (new_status, pick))
                conn.commit(); conn.close()
                st.success("Status Updated.")
                safe_rerun()
        else:
            st.info("No status column to update.")

        if st.button("Delete Ticket"):
            conn = get_conn()
            conn.execute(f"DELETE FROM it_tickets WHERE {id_col}=?", (pick,))
            conn.commit(); conn.close()
            st.success("Ticket Deleted.")
            safe_rerun()
    else:
        st.info("No tickets found.")
else:
    st.info("You have read-only access. Only admins can modify tickets.")

st.divider()
st.subheader("Add New Ticket")
if st.session_state.get("role") == "admin":
    with st.form("add_ticket", clear_on_submit=True):
        t_id = st.text_input("Ticket ID (optional)")
        t_title = st.text_input("Title")
        t_priority = st.selectbox("Priority", ["low","medium","high"])
        t_status = st.selectbox("Status", ["open","in_progress","closed"])
        t_assignee = st.text_input("Assignee")
        t_description = st.text_area("Description")
        t_resolution = st.number_input("Resolution Time (hrs)", min_value=0.0, value=0.0, step=1.0)
        submitted = st.form_submit_button("Add Ticket")
        if submitted:
            # build insert for present columns only
            to_insert = {}
            if "ticket_id" in cols: to_insert["ticket_id"] = (t_id or None)
            if "priority" in cols: to_insert["priority"] = t_priority
            if "status" in cols: to_insert["status"] = t_status
            if "assigned_to" in cols or "assignee" in cols:
                key = "assigned_to" if "assigned_to" in cols else "assignee"
                to_insert[key] = t_assignee
            if "description" in cols: to_insert["description"] = t_description
            if "resolution_time_hours" in cols: to_insert["resolution_time_hours"] = float(t_resolution)
            # created_at fallback is set to datetime('now') in SQL if present
            columns_sql = ", ".join(to_insert.keys())
            placeholders = ", ".join(["?"] * len(to_insert))
            values = list(to_insert.values())
            conn = get_conn()
            if columns_sql:
                conn.execute(f"INSERT INTO it_tickets ({columns_sql}) VALUES ({placeholders})", values)
            else:
                # nothing matched; just insert created_at if that column exists
                if "created_at" in cols:
                    conn.execute("INSERT INTO it_tickets (created_at) VALUES (datetime('now'))")
                else:
                    # can't insert anything sensible
                    st.error("No matching columns in table to insert data.")
            conn.commit(); conn.close()
            st.success("Ticket Added.")
            safe_rerun()
