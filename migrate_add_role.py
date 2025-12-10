import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "db" / "data.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check if role column exists
cur.execute("PRAGMA table_info(users)")
cols = [c[1] for c in cur.fetchall()]

if "role" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    conn.commit()
    print("Role column added successfully.")
else:
    print("Role column already exists.")

conn.close()
