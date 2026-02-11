import os
from sqlalchemy import create_engine, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import ARRAY

SQLALCHEMY_DATABASE_URL = os.getenv("DB_URL")

# For testing workaround: if DB_URL is explicitly None during import, usage of engine will fail.
if not SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Helper to choose ARRAY or JSON based on environment
def PortableArray(item_type):
    # This check happens at module import time
    db_url = os.getenv("DB_URL", "")
    if "postgres" in db_url:
        return ARRAY(item_type)
    return JSON

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
