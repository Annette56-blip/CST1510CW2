import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
import matplotlib.pyplot as plt

# --- Access control ---
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("You must be logged in to view this page.")
    st.stop()

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "data.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

st.title("🛠 IT Operations Dashboard")

conn = get_conn()

try:
    df = pd.read_sql("SELECT rowid AS id, * FROM it_tickets", conn)
except Exception:
    st.error("Table it_tickets not found. Run your ingestion script!")
    conn.close()
    st.stop()

conn.close()

# KPIs
k1, k2, k3 = st.columns(3)
k1.metric("Total Tickets", len(df))
k2.metric("Open Tickets", int((df["status"] == "open").sum()))
avg_res = df["resolution_time_hours"].dropna()
k3.metric("Avg Resolution (hrs)", f"{avg_res.mean():.1f}" if not avg_res.empty else "N/A")

st.divider()

# Charts
col1, col2 = st.columns((2, 3))

with col1:
    st.subheader("Priority Distribution")
    pri_counts = df["priority"].value_counts()
    fig1, ax1 = plt.subplots()
    ax1.bar(pri_counts.index, pri_counts.values)
    st.pyplot(fig1)

with col2:
    st.subheader("Status Breakdown")
    stat_counts = df["status"].value_counts()
    fig2, ax2 = plt.subplots()
    ax2.pie(stat_counts.values, labels=stat_counts.index, autopct="%1.1f%%")
    st.pyplot(fig2)

st.divider()
st.subheader("Tickets Table")
st.dataframe(df, height=300)

# Update or delete ticket
st.subheader("Update / Delete Ticket")

if st.session_state.get("role") == "admin":

    if not df.empty:
        pick = st.selectbox("Choose Ticket ID:", df["id"].tolist())
        chosen = df[df["id"] == pick].iloc[0]
        st.write("Selected:", chosen.to_dict())

        new_status = st.selectbox("New Status:", ["open", "in_progress", "closed"], index=0)

        if st.button("Update Status"):
            conn = get_conn()
            conn.execute("UPDATE it_tickets SET status=? WHERE rowid=?", (new_status, pick))
            conn.commit()
            conn.close()
            st.success("Status Updated.")
            st.experimental_set_query_params(_=None)
            st.rerun()

        if st.button("Delete Ticket"):
            conn = get_conn()
            conn.execute("DELETE FROM it_tickets WHERE rowid=?", (pick,))
            conn.commit()
            conn.close()
            st.success("Ticket Deleted.")
            st.experimental_set_query_params(_=None)
            st.rerun()

    else:
        st.info("No tickets found.")

else:
    st.info("You have read-only access. Only admins can modify tickets.")


st.divider()
st.subheader("Add New Ticket")

if st.session_state.get("role") == "admin":

    with st.form("add_ticket", clear_on_submit=True):
        t_title = st.text_input("Title")
        t_priority = st.selectbox("Priority", ["low", "medium", "high"])
        t_status = st.selectbox("Status", ["open", "in_progress", "closed"])
        t_assignee = st.text_input("Assignee")
        t_description = st.text_area("Description")
        t_resolution = st.number_input("Resolution Time (hrs)", min_value=0.0, value=0.0, step=1.0)

        submitted = st.form_submit_button("Add Ticket")

        if submitted:
            conn = get_conn()
            conn.execute(
                """
                INSERT INTO it_tickets
                (title, priority, status, assignee, description, resolution_time_hours, created_date)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    t_title,
                    t_priority,
                    t_status,
                    t_assignee,
                    t_description,
                    float(t_resolution),
                ),
            )
            conn.commit()
            conn.close()
            st.success("Ticket Added.")
            st.experimental_set_query_params(_=None)
            st.rerun()

else:
    st.info("Only admins can add new tickets.")

