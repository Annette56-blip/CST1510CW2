# pages/3_Data_Governance.py
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

st.title("📊 Data Governance & Metadata Dashboard")

conn = get_conn()
try:
    df = pd.read_sql("SELECT * FROM datasets_metadata", conn)
except Exception:
    st.error("Table datasets_metadata not found. Run your ingestion script!")
    conn.close()
    st.stop()
finally:
    conn.close()

# columns present: dataset_id, name, rows, columns, uploaded_by, uploaded_at — but be flexible
cols = {c.lower(): c for c in df.columns}
dataset_id_col = cols.get("dataset_id", cols.get("id", None))
name_col = cols.get("name")
rows_col = cols.get("rows")
cols_col = cols.get("columns")
uploader_col = cols.get("uploaded_by")
uploaded_at_col = cols.get("uploaded_at")

# cast dataset_id to string to avoid Arrow int conversion errors
if dataset_id_col and dataset_id_col in df.columns:
    df[dataset_id_col] = df[dataset_id_col].astype(str)

st.subheader("Datasets Metadata Overview")
st.dataframe(df, height=300)

# KPIs
k1, k2, k3 = st.columns(3)
k1.metric("Total Datasets", len(df))
if rows_col and rows_col in df.columns:
    safe_rows = pd.to_numeric(df[rows_col], errors="coerce").dropna()
    avg_rows = safe_rows.mean() if not safe_rows.empty else 0
    k2.metric("Avg Rows", f"{avg_rows:.0f}")
else:
    k2.metric("Avg Rows", "N/A")

if uploaded_at_col and uploaded_at_col in df.columns:
    try:
        df[uploaded_at_col] = pd.to_datetime(df[uploaded_at_col], errors="coerce")
        k3.metric("Most Recent Upload", str(df[uploaded_at_col].max()))
    except Exception:
        k3.metric("Most Recent Upload", str(df[uploaded_at_col].max()))
else:
    k3.metric("Most Recent Upload", "N/A")

st.divider()

st.subheader("Dataset Category / Size (if present)")
if "category" in df.columns:
    cat_counts = df["category"].fillna("UNKNOWN").value_counts()
    chart_df = pd.DataFrame({"Category": cat_counts.index, "Count": cat_counts.values})
    st.bar_chart(chart_df.rename(columns={"Category":"index"}).set_index("index"))
else:
    st.info("No 'category' column found. Showing dataset row counts by name instead.")
    if rows_col and name_col in df.columns:
        try:
            series = pd.to_numeric(df[rows_col], errors="coerce").fillna(0)
            idx = pd.Series(series.values, index=df[name_col]).sort_values(ascending=False)
            st.bar_chart(idx)
        except Exception:
            st.info("Unable to render rows chart due to data types.")

st.divider()
st.subheader("Add New Metadata Entry")
with st.form("add_metadata", clear_on_submit=True):
    ds_id = st.text_input("Dataset ID (optional)")
    ds_name = st.text_input("Dataset Name")
    ds_rows = st.number_input("Rows", min_value=0, value=0, step=1)
    ds_cols = st.number_input("Columns", min_value=0, value=0, step=1)
    ds_uploaded_by = st.text_input("Uploaded By")
    ds_uploaded_at = st.date_input("Uploaded At")
    submitted = st.form_submit_button("Add Metadata")
    if submitted:
        to_insert = {}
        if "dataset_id" in cols: to_insert["dataset_id"] = (ds_id or None)
        if "name" in cols: to_insert["name"] = ds_name
        if "rows" in cols: to_insert["rows"] = int(ds_rows)
        if "columns" in cols: to_insert["columns"] = int(ds_cols)
        if "uploaded_by" in cols: to_insert["uploaded_by"] = ds_uploaded_by
        if "uploaded_at" in cols: to_insert["uploaded_at"] = str(ds_uploaded_at)
        conn = get_conn()
        if to_insert:
            columns_sql = ", ".join(to_insert.keys())
            placeholders = ", ".join(["?"] * len(to_insert))
            values = list(to_insert.values())
            conn.execute(f"INSERT INTO datasets_metadata ({columns_sql}) VALUES ({placeholders})", values)
            conn.commit()
            conn.close()
            st.success("Metadata added — refresh the page")
            safe_rerun()
        else:
            st.error("No matching columns in datasets_metadata to insert into.")
st.divider()
st.download_button(
    "Export Metadata CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="datasets_metadata.csv",
    mime="text/csv"
)
