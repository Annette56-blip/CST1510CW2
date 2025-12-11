import sqlite3
from pathlib import Path

# Path to the SQLite database (relative to this script's folder)
DB_PATH = Path(__file__).resolve().parent / "db" / "data.db"

# Open database connection + cursor for executing SQL commands
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# CHECK WHETHER THE 'role' COLUMN EXISTS IN THE users TABLE

# PRAGMA table_info returns metadata for each column in the table
cur.execute("PRAGMA table_info(users)")

# Extract only the column names from the metadata
cols = [c[1] for c in cur.fetchall()]

# If 'role' is not present, add it with a default value
if "role" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    conn.commit()  # persist schema change
    print("Role column added successfully.")

# If it already exists, do nothing — just inform the user
else:
    print("Role column already exists.")

# Close DB connection to avoid leaving open handles
conn.close()
