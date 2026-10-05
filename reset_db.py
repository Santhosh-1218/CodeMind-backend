import os
import sqlite3
from app.core.config import settings

def reset_database():
    db_url = settings.DATABASE_URL
    print(f"[*] Resetting database at: {db_url}")
    
    if "sqlite" in db_url:
        raw_db_path = db_url.replace("sqlite:///", "")
        if os.path.exists(raw_db_path):
            os.remove(raw_db_path)
            print(f"[✓] Removed SQLite database file: {raw_db_path}")
        else:
            print("[i] Database file does not exist yet.")
    
    from app.db.database import init_db
    init_db()
    print("[✓] Re-initialized fresh database schema with all OWASP, CWE, and status tables.")

if __name__ == "__main__":
    reset_database()
