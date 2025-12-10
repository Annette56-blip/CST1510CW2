import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
import matplotlib.pyplot as plt

# --- Access control: user must be logged in ---
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("You must be logged in to view this page.")
    st.stop()

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "data.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

st.title("🔒 Cyber Dashboard")

conn = get_conn()

try:
    df = pd.read_sql("SELECT rowid AS id, * FROM cyber_incidents", conn)
except Exception:
    st.error("Table cyber_incidents not found. Run your ingestion script!")
    conn.close()
    st.stop()

conn.close()

# KPIs
k1, k2, k3 = st.columns(3)
k1.metric("Total incidents", len(df))
k2.metric("Open incidents", int((df['status'] == 'open').sum()))
avg_res = df['resolution_time_hours'].dropna()
k3.metric("Avg resolution (hrs)", f"{avg_res.mean():.1f}" if not avg_res.empty else "N/A")

st.divider()

st.subheader("Severity distribution")
severity_counts = df['severity'].value_counts()
fig1, ax1 = plt.subplots()
ax1.bar(severity_counts.index, severity_counts.values)
st.pyplot(fig1)

st.subheader("Incidents")
st.dataframe(df)
st.divider()
st.subheader("Admin Tools")

# Check role (must be logged in AND must have role in session)
if st.session_state.get("role") == "admin":

    # --- UPDATE INCIDENT STATUS ---
    st.markdown("### Update Incident Status")

    pick = st.selectbox("Choose Incident ID", df["id"].tolist())
    chosen = df[df["id"] == pick].iloc[0]
    st.write("Selected incident:", chosen.to_dict())

    new_status = st.selectbox("New Status", ["open", "in_progress", "closed"])

    if st.button("Update Status"):
        conn = get_conn()
        conn.execute(
            "UPDATE cyber_incidents SET status=? WHERE rowid=?",
            (new_status, pick)
        )
        conn.commit()
        conn.close()
        st.success("Incident updated.")
        st.experimental_set_query_params(_=None)
        st.rerun()


    # --- DELETE INCIDENT ---
    st.markdown("### Delete Incident")

    if st.button("Delete Incident"):
        conn = get_conn()
        conn.execute("DELETE FROM cyber_incidents WHERE rowid=?", (pick,))
        conn.commit()
        conn.close()
        st.success("Incident deleted.")
        st.experimental_set_query_params(_=None)
        st.rerun()



    # --- ADD NEW INCIDENT ---
    st.markdown("### Add New Incident")

    with st.form("add_incident", clear_on_submit=True):

        t_title = st.text_input("Title")
        t_severity = st.selectbox("Severity", ["low", "medium", "high", "critical"])
        t_status = st.selectbox("Status", ["open", "in_progress", "closed"])
        t_reporter = st.text_input("Reporter")
        t_notes = st.text_area("Notes")
        t_resolution = st.number_input(
            "Resolution Time (hrs)", min_value=0.0, step=1.0
        )

        submitted = st.form_submit_button("Add Incident")

        if submitted:
            conn = get_conn()
            conn.execute("""
                INSERT INTO cyber_incidents
                (title, severity, status, reporter, notes, resolution_time_hours)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (t_title, t_severity, t_status, t_reporter, t_notes, float(t_resolution))
            )
            conn.commit()
            conn.close()
            st.success("Incident added.")
            st.experimental_set_query_params(_=None)
            st.rerun()

else:
    st.info("You are in read-only mode. Only admins can modify incidents.")
