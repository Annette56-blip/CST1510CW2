import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
import matplotlib.pyplot as plt

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "data.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

st.title("📊 Data Governance & Metadata Dashboard")

# Load metadata table
conn = get_conn()
try:
    df = pd.read_sql("SELECT rowid AS id, * FROM datasets_metadata", conn)
except Exception:
    st.error("Table datasets_metadata not found. Run your ingestion script!")
    conn.close()
    st.stop()
conn.close()

st.subheader("Datasets Metadata Overview")
st.dataframe(df, height=300)

# KPIs
k1, k2, k3 = st.columns(3)
k1.metric("Total Datasets", len(df))
k2.metric("Avg Dataset Size (MB)", f"{df['size'].mean():.1f}" if not df['size'].empty else "0")
recent = df["uploaded_at"].max()
k3.metric("Most Recent Upload", recent if pd.notna(recent) else "N/A")

st.divider()

# Category distribution
st.subheader("Dataset Category Distribution")
category_counts = df["category"].value_counts()

fig1, ax1 = plt.subplots(figsize=(6,4))
ax1.bar(category_counts.index, category_counts.values)
ax1.set_xlabel("Category")
ax1.set_ylabel("Count")
ax1.set_title("Datasets by Category")
st.pyplot(fig1)

# Size distribution
st.subheader("Dataset Size Distribution")
fig2, ax2 = plt.subplots(figsize=(6,4))
ax2.hist(df["size"], bins=5)
ax2.set_xlabel("Size (MB)")
ax2.set_ylabel("Frequency")
st.pyplot(fig2)

st.divider()
st.subheader("Add New Metadata Entry")

with st.form("add_metadata", clear_on_submit=True):
    name = st.text_input("Dataset Name")
    source = st.text_input("Source")
    category = st.text_input("Category")
    size = st.number_input("Size (MB)", min_value=0.0, step=10.0)
    uploaded_at = st.date_input("Uploaded At")

    submitted = st.form_submit_button("Add Metadata")

    if submitted:
        conn = get_conn()
        conn.execute(
            """
            INSERT INTO datasets_metadata (name, source, category, size, uploaded_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, source, category, size, str(uploaded_at)),
        )
        conn.commit()
        conn.close()
        st.success("Metadata added — refresh the page")

st.divider()
st.download_button(
    "Export Metadata CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="datasets_metadata.csv",
    mime="text/csv"
)
