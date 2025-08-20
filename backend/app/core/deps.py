# import redi/s
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings

# --- Database Session Dependency ---
def get_db():
    """
    Dependency function that creates and yields a new database session
    for each request. 
    
    This is a standard FastAPI pattern for managing database sessions. It ensures 
    that the session is always closed after the request is finished, even if 
    an error occurs.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


