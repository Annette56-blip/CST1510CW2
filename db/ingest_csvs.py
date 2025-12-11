import sqlite3
from pathlib import Path
import pandas as pd

# Resolve project root folder and define paths to data and database
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "DATA"            # Folder containing CSV files
DB_PATH = ROOT / "db" / "data.db"   # SQLite database file

def ingest():
    # Open a connection to the SQLite database
    conn = sqlite3.connect(DB_PATH)
    print(f"Using DB: {DB_PATH}")

    # Loop through every CSV file in the DATA directory
    for csv_file in DATA_DIR.glob("*.csv"):
        print(f"\nReading {csv_file.name}")

        # Load the CSV into a DataFrame
        df = pd.read_csv(csv_file)

        # Use the CSV filename (without extension) as table name
        # Replace '-' with '_' to keep it SQL-friendly
        table = csv_file.stem.replace("-", "_")

        print(df.head())  # Preview first few rows for sanity check

        # Write DataFrame to SQLite table (overwrite if it already exists)
        df.to_sql(table, conn, if_exists="replace", index=False)
        print(f"Imported → {table}")

    # Close the database connection once all files are processed
    conn.close()
    print("\nDONE — all CSVs imported successfully.")

if __name__ == "__main__":
    # Entry point to run ingestion when script is executed directly
    ingest()
