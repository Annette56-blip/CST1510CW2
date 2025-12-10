import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "DATA"
DB_PATH = ROOT / "db" / "data.db"

def ingest():
    conn = sqlite3.connect(DB_PATH)
    print(f"Using DB: {DB_PATH}")

    for csv_file in DATA_DIR.glob("*.csv"):
        print(f"\nReading {csv_file.name}")
        df = pd.read_csv(csv_file)
        table = csv_file.stem.replace("-", "_")
        print(df.head())
        df.to_sql(table, conn, if_exists="replace", index=False)
        print(f"Imported → {table}")

    conn.close()
    print("\nDONE — all CSVs imported successfully.")

if __name__ == "__main__":
    ingest()
