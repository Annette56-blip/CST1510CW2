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

# --- PROPER SESSION INITIALIZATION ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None

# --- CONFIG ---
ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "db" / "data.db"

# --- PASSWORD HASHING (PBKDF2) ---
ITERATIONS = 100_000
SALT_BYTES = 16
HASH_NAME = "sha256"

def hash_password(password: str, salt: bytes = None):
    if salt is None:
        salt = os.urandom(SALT_BYTES)
    pwd = password.encode("utf-8")
    dk = hashlib.pbkdf2_hmac(HASH_NAME, pwd, salt, ITERATIONS)
    return binascii.hexlify(salt).decode(), binascii.hexlify(dk).decode()

def verify_password(salt_hex, stored_hash_hex, password_attempt):
    salt = binascii.unhexlify(salt_hex.encode())
    _, attempt_hash = hash_password(password_attempt, salt)
    return attempt_hash == stored_hash_hex

# --- DATABASE HELPERS ---
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_user_table():
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
        return False
    finally:
        conn.close()

def authenticate(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT salt, pw_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    salt_hex, hash_hex = row
    return verify_password(salt_hex, hash_hex, password)

# --- GENERIC TABLE READING ---
def list_tables():
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
    conn = get_conn()
    df = pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
    conn.close()
    return df

def update_status(table, pk_col, pk_value, new_status):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f'UPDATE "{table}" SET status=? WHERE "{pk_col}"=?',
        (new_status, pk_value),
    )
    conn.commit()
    conn.close()

# --- STREAMLIT PAGE CONFIG ---
st.set_page_config(page_title="Cyber Ops Dashboard", layout="wide")
init_user_table()

# --- SIDEBAR AUTH ---
with st.sidebar:
    st.title("Auth")

    if not st.session_state.logged_in:
        action = st.radio("Action", ["Login", "Register"], index=0)

        # --- LOGIN ---
        if action == "Login":
            uname = st.text_input("Username")
            pwd = st.text_input("Password", type="password")

            if st.button("Login"):
                if authenticate(uname, pwd):
                    st.session_state.logged_in = True
                    st.session_state.username = uname

                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("SELECT role FROM users WHERE username=?", (uname,))
                    st.session_state.role = cur.fetchone()[0]
                    conn.close()

                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        # --- REGISTER ---
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

    else:
        st.markdown(f"**User:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.role}")

        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

# --- MAIN AREA: SHOW DASHBOARD ONLY IF LOGGED IN ---
if not st.session_state.logged_in:
    st.title("Please log in")
    st.info("Use the sidebar to log in or register.")
    st.stop()

st.header("Cyber Ops — Dashboard")

left, right = st.columns([1, 3])

with left:
    st.subheader("Data Tables")
    tables = list_tables()

    if not tables:
        st.error("No data found. Run ingestion script.")
        st.stop()

    table = st.selectbox("Select Table", tables)

    if st.button("Refresh"):
        st.rerun()

    df_sample = read_table(table)

    if "status" in df_sample.columns:
        st.markdown("---")
        st.write("Quick Status Update")

        pk_candidates = [c for c in df_sample.columns if c.lower().endswith("id")] or [df_sample.columns[0]]
        pk_col = pk_candidates[0]

        pk_value = st.selectbox("Choose ID", df_sample[pk_col].tolist())
        new_status = st.selectbox("New Status", ["open", "in_progress", "closed", "resolved"])

        if st.button("Apply Update"):
            update_status(table, pk_col, pk_value, new_status)
            st.success("Status updated!")
            st.experimental_set_query_params(_=None)
            st.rerun()

with right:
    df = read_table(table)
    st.subheader(f"Preview: {table} ({len(df)} rows)")
    st.dataframe(df)

    if "severity" in df.columns:
        st.subheader("Severity Distribution")
        vc = df["severity"].fillna("UNKNOWN").value_counts()
        fig, ax = plt.subplots()
        vc.plot(kind="bar", ax=ax)
        st.pyplot(fig)
