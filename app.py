# app.py
import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
import os
import hashlib
import binascii
import datetime
import matplotlib.pyplot as plt

# INITIALIZE SESSION STATE KEYS (avoids key errors later)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None

# APP CONFIG PATHS
ROOT = Path(__file__).resolve().parent         # app root folder
DB_PATH = ROOT / "db" / "data.db"              # SQLite DB location

# PASSWORD SECURITY SETTINGS (PBKDF2)
ITERATIONS = 100_000     # how many hashing rounds → slows brute force
SALT_BYTES = 16           # random salt length
HASH_NAME = "sha256"      # underlying hash algorithm

def hash_password(password: str, salt: bytes = None):
    # Hashes a password using PBKDF2; returns salt + derived key as hex strings
    if salt is None:
        salt = os.urandom(SALT_BYTES)  # generate random salt for new users
    pwd = password.encode("utf-8")
    dk = hashlib.pbkdf2_hmac(HASH_NAME, pwd, salt, ITERATIONS)
    return binascii.hexlify(salt).decode(), binascii.hexlify(dk).decode()

def verify_password(salt_hex, stored_hash_hex, password_attempt):
    # Recreate the hash using stored salt and compare
    salt = binascii.unhexlify(salt_hex.encode())
    _, attempt_hash = hash_password(password_attempt, salt)
    return attempt_hash == stored_hash_hex

# DATABASE UTILITIES
def get_conn():
    # Ensures DB directory exists, returns thread-safe SQLite connection
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_user_table():
    # Creates the user table if missing → ensures login system works
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            salt TEXT NOT NULL,
            pw_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    """)
    conn.commit()
    conn.close()

def create_user(username, password, role="user"):
    # Registers a new user with hashed password and role
    conn = get_conn()
    cur = conn.cursor()
    salt_hex, hash_hex = hash_password(password)
    try:
        cur.execute("""
            INSERT INTO users (username, salt, pw_hash, created_at, role)
            VALUES (?, ?, ?, ?, ?)
        """, (username, salt_hex, hash_hex, datetime.datetime.utcnow().isoformat(), role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Username already exists
        return False
    finally:
        conn.close()

def authenticate(username, password):
    # Fetch stored hash + salt, verify password, return True/False
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT salt, pw_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    salt_hex, hash_hex = row
    return verify_password(salt_hex, hash_hex, password)

# GENERIC TABLE MANAGEMENT (for dashboards)
def list_tables():
    # Return all non-system tables except 'users'
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='users'
    """)
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

def read_table(table):
    # Read any table into a pandas DataFrame
    conn = get_conn()
    df = pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
    conn.close()
    return df

def update_status(table, pk_col, pk_value, new_status):
    # Update the status column of a chosen record
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f'UPDATE "{table}" SET status=? WHERE "{pk_col}"=?',
        (new_status, pk_value),
    )
    conn.commit()
    conn.close()

# STREAMLIT CONFIG + USER TABLE INIT
st.set_page_config(page_title="Cyber Ops Dashboard", layout="wide")
init_user_table()     # ensures authentication always works on startup

# SIDEBAR AUTH BLOCK (Login / Register)
with st.sidebar:
    st.title("Auth")

    # Not logged in: show login/register options
    if not st.session_state.logged_in:
        action = st.radio("Action", ["Login", "Register"], index=0)

        # LOGIN
        if action == "Login":
            uname = st.text_input("Username")
            pwd = st.text_input("Password", type="password")

            if st.button("Login"):
                if authenticate(uname, pwd):
                    # Persist login state
                    st.session_state.logged_in = True
                    st.session_state.username = uname

                    # Load user role from DB
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("SELECT role FROM users WHERE username=?", (uname,))
                    st.session_state.role = cur.fetchone()[0]
                    conn.close()

                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        # REGISTER 
        else:
            newu = st.text_input("Choose Username")
            newp = st.text_input("Choose Password", type="password")
            newp2 = st.text_input("Repeat Password", type="password")
            new_role = st.selectbox("Role", ["user", "admin"])

            if st.button("Register"):
                if not newu or not newp:
                    st.error("All fields required.")
                elif newp != newp2:
                    st.error("Passwords do not match.")
                else:
                    if create_user(newu, newp, new_role):
                        st.success("User created successfully.")
                    else:
                        st.error("Username already exists.")

    # Logged in: show logout + info
    else:
        st.markdown(f"**User:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.role}")

        if st.button("Logout"):
            st.session_state.clear()  # wipe all session keys
            st.rerun()

# MAIN DASHBOARD AREA (Requires login)
if not st.session_state.logged_in:
    # User not authenticated → block dashboard
    st.title("Please log in")
    st.info("Use the sidebar to log in or register.")
    st.stop()

st.header("Cyber Ops — Dashboard")

left, right = st.columns([1, 3])

# LEFT PANEL — TABLE SELECTION + STATUS UPDATE TOOL
with left:
    st.subheader("Data Tables")
    tables = list_tables()

    if not tables:
        st.error("No data found. Run ingestion script.")
        st.stop()

    # Pick which database table to view
    table = st.selectbox("Select Table", tables)

    if st.button("Refresh"):
        st.rerun()

    df_sample = read_table(table)

    # If table contains a 'status' column → show quick update controls
    if "status" in df_sample.columns:
        st.markdown("---")
        st.write("Quick Status Update")

        # Pick primary key column (anything ending with 'id')
        pk_candidates = [c for c in df_sample.columns if c.lower().endswith("id")] or [df_sample.columns[0]]
        pk_col = pk_candidates[0]

        # User selects record ID + new status
        pk_value = st.selectbox("Choose ID", df_sample[pk_col].tolist())
        new_status = st.selectbox("New Status", ["open", "in_progress", "closed", "resolved"])

        if st.button("Apply Update"):
            update_status(table, pk_col, pk_value, new_status)
            st.success("Status updated!")
            st.experimental_set_query_params(_=None)  # ensure clean URL
            st.rerun()

# RIGHT PANEL — DATA PREVIEW + OPTIONAL CHARTS
with right:
    df = read_table(table)
    st.subheader(f"Preview: {table} ({len(df)} rows)")
    st.dataframe(df)

    # If table includes severity → plot a quick interactive distribution chart
if "severity" in df.columns:
    st.subheader("Severity Distribution (Interactive)")

    vc = df["severity"].fillna("UNKNOWN").value_counts()

    chart_df = pd.DataFrame({
        "Severity": vc.index,
        "Count": vc.values
    })

    st.bar_chart(chart_df, x="Severity", y="Count")

