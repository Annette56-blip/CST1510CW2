import sqlite3
conn = sqlite3.connect("db/data.db")
cur = conn.cursor()

cur.execute("PRAGMA table_info(datasets_metadata)")
for row in cur.fetchall():
    print(row)
