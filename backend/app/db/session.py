from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from app.core.config import settings

# Create the SQLAlchemy engine.
# The `connect_args` is specific to SQLite and is needed to allow
# the same connection to be used across different threads, which is
# a requirement for FastAPI's dependency injection system with background tasks.
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# Create a configured "Session" class.
# This is not a session instance, but a factory for creating them.
# autocommit=False and autoflush=False are standard settings for
# web applications, giving more control over transaction management.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for our SQLAlchemy models to inherit from.
# All of our schema/table models will be subclasses of this Base.
Base = declarative_base()

# --- Dependency for getting a DB session ---
def get_db():
    """
    A dependency function that creates and yields a new database session
    for each request. It ensures the session is always closed, even if
    an error occurs. This is a standard pattern for managing database
    sessions in FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
