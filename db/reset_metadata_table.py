import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "data.db"

print("DB PATH USED:", DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Dropping table datasets_metadata…")
cur.execute("DROP TABLE IF EXISTS datasets_metadata;")

conn.commit()
conn.close()

print("DONE — Table successfully dropped.")
