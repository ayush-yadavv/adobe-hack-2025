from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import sys 

# Configure logging for the entire application at the very beginning
logging.basicConfig(
    level=logging.DEBUG, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)] 
)
logger = logging.getLogger(__name__)
logger.debug("Application startup: Initializing FastAPI application.")

# Load environment variables from .env file, specifying the path
# Assumes .env is in the 'backend' directory relative to the project root
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env") 
load_dotenv(dotenv_path=dotenv_path)

# Debugging: Check if GOOGLE_API_KEY is loaded
loaded_api_key = os.getenv("GOOGLE_API_KEY")
logger.debug(f"DEBUG: main.py: GOOGLE_API_KEY after load_dotenv: {bool(loaded_api_key)}")
print(f"RAW PRINT: GOOGLE_API_KEY after load_dotenv: {bool(loaded_api_key)}") # Fallback print

# Import settings and database session management
from app.core.config import settings
from app.db.session import engine, Base
logger.debug("Main: Imported settings and database session management.")

# Import the API routers for each resource
from app.api.v1 import collections, documents, recommendation, insights, podcast
logger.debug("Main: Imported API routers.")

# --- Database Table Creation ---
# This function will create all the tables defined by our SQLAlchemy models
# in the database. It's good practice to call this when the application starts.
def create_tables():
    """
    Creates all database tables based on the SQLAlchemy Base metadata.
    """
    Base.metadata.create_all(bind=engine)

# Create the main FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)
logger.debug(f"Main: FastAPI application instance created with title '{settings.PROJECT_NAME}'.")

# --- Middleware ---
# Set up CORS (Cross-Origin Resource Sharing) middleware.
# This is important for allowing your frontend application (running on a
# different domain or port) to communicate with this API.
# The settings below are permissive; for production, you should restrict
# the allowed origins to your specific frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
logger.debug("Main: CORS middleware added.")

# Mount static files directory
app.mount("/storage", StaticFiles(directory="backend/storage"), name="storage")
logger.debug("Main: Mounted static files directory at '/storage'")

# --- Event Handlers ---
@app.on_event("startup")
def on_startup():
    """
    Event handler that runs when the FastAPI application starts.
    This is the perfect place to create our database tables.
    """
    logger.debug("Main: Startup event triggered. Creating database tables.")
    create_tables()

# --- API Routers ---
# Include the routers from our API modules.
# Each router's endpoints will be prefixed accordingly.
app.include_router(collections.router, prefix=f"{settings.API_V1_STR}/collections", tags=["Collections"])
logger.debug(f"Main: Including collections router with prefix: {settings.API_V1_STR}/collections")
app.include_router(documents.router, prefix=f"{settings.API_V1_STR}/documents", tags=["Documents"])
logger.debug(f"Main: Including documents router with prefix: {settings.API_V1_STR}/documents")
app.include_router(recommendation.router, prefix=f"{settings.API_V1_STR}/recommendations", tags=["Recommendations"])
logger.debug(f"Main: Including recommendation router with prefix: {settings.API_V1_STR}/recommendations")
app.include_router(insights.router, prefix=f"{settings.API_V1_STR}/insights", tags=["Insights"])
logger.debug(f"Main: Including insights router with prefix: {settings.API_V1_STR}/insights")
app.include_router(podcast.router, prefix=f"{settings.API_V1_STR}/podcasts", tags=["Podcasts"])
logger.debug(f"Main: Including podcast router with prefix: {settings.API_V1_STR}/podcasts")

# --- Root Endpoint ---
@app.get("/", tags=["Root"])
def read_root():
    """
    A simple root endpoint for health checks and to welcome users.
    """
    return {"message": f"Welcome to the {settings.PROJECT_NAME}"}
