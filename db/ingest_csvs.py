import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "DATA"
DB_PATH = ROOT / "db" / "data.db"

def ingest():
    conn = sqlite3.connect(DB_PATH)
    print(f"Using DB: {DB_PATH}")

    # ---------------- CYBER INCIDENTS ----------------
    cyber = pd.read_csv(DATA_DIR / "cyber_incidents.csv")

    cyber = cyber.rename(columns={
        "incident_id": "incident_id",
        "timestamp": "timestamp",
        "severity": "severity",
        "category": "category",
        "status": "status",
        "description": "notes"
    })

    cyber.to_sql("cyber_incidents", conn, if_exists="replace", index=False)
    print("Imported: cyber_incidents")

    # ---------------- IT TICKETS ----------------
    it = pd.read_csv(DATA_DIR / "it_tickets.csv")

    it = it.rename(columns={
        "ticket_id": "ticket_id",
        "priority": "priority",
        "description": "description",
        "status": "status",
        "assigned_to": "assignee",
        "created_at": "created_at",
        "resolution_time_hours": "resolution_time_hours"
    })

    it.to_sql("it_tickets", conn, if_exists="replace", index=False)
    print("Imported: it_tickets")

    # ---------------- DATASETS METADATA ----------------
    meta = pd.read_csv(DATA_DIR / "datasets_metadata.csv")

    meta = meta.rename(columns={
        "dataset_id": "dataset_id",
        "name": "name",
        "rows": "rows",
        "columns": "columns",
        "uploaded_by": "uploaded_by",
        "upload_date": "uploaded_at"
    })

    meta.to_sql("datasets_metadata", conn, if_exists="replace", index=False)
    print("Imported: datasets_metadata")

    conn.close()
    print("\nDONE — database successfully refreshed!")

if __name__ == "__main__":
    ingest()
