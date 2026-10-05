import os
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Ensure data directory exists
db_path = settings.DATABASE_URL.replace("sqlite:///", "")
if db_path and os.path.dirname(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app.models.user import User
    from app.models.oauth_account import OAuthAccount
    from app.models.session import Session
    from app.models.project import Project
    from app.models.review import Review
    from app.models.finding import Finding
    from app.models.review_file import ReviewFile
    
    Base.metadata.create_all(bind=engine)
    
    # Lightweight schema migration for SQLite table columns
    if "sqlite" in settings.DATABASE_URL:
        import sqlite3
        raw_db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(raw_db_path):
            try:
                conn = sqlite3.connect(raw_db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(findings)")
                existing_cols = [row[1] for row in cursor.fetchall()]
                needed_cols = {
                    "line_end": "INTEGER",
                    "confidence": "INTEGER DEFAULT 85",
                    "evidence": "TEXT",
                    "memory_influenced": "BOOLEAN DEFAULT 0",
                    "hindsight_memory_text": "TEXT",
                    "owasp_category": "TEXT",
                    "cwe_id": "TEXT",
                    "status": "TEXT DEFAULT 'open'",
                    "assigned_to": "TEXT"
                }
                for col, col_type in needed_cols.items():
                    if col not in existing_cols:
                        cursor.execute(f"ALTER TABLE findings ADD COLUMN {col} {col_type}")

                cursor.execute("PRAGMA table_info(oauth_accounts)")
                oauth_cols = [row[1] for row in cursor.fetchall()]
                if "access_token" not in oauth_cols:
                    cursor.execute("ALTER TABLE oauth_accounts ADD COLUMN access_token TEXT")

                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[init_db] SQLite auto-migration notice: {e}")

