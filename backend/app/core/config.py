import os
from pydantic_settings import BaseSettings
from typing import List, Optional

# Get the root path of the project (the 'backend' directory)
# This assumes the script is run from the 'backend' directory.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Settings(BaseSettings):
    """
    Pydantic settings class to manage application configuration.
    It automatically reads environment variables from a .env file.
    """
    # --- Core Application Settings ---
    PROJECT_NAME: str = "AI Document Analysis API"
    API_V1_STR: str = "/api/v1"

    
    # --- Database Settings ---
    # The default URL points to a SQLite database file in the project's backend root.
    DATABASE_URL: str = f"sqlite:///{os.path.join(PROJECT_ROOT, 'app.db')}"

    # --- Storage Settings ---
    # The base path for local storage. In a containerized environment, this
    # path should be mounted to a persistent volume.
    STORAGE_PATH: str = os.path.join(PROJECT_ROOT, "storage")
    BASE_URL: str = "http://localhost:8000"
    
    # --- ML Model Settings ---
    # The name of the sentence transformer model to be used for embeddings.
    # We are using a larger, more accurate model for better semantic search quality.
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-mpnet-base-v2"

    # --- Redis Settings ---
  

    # --- TTS Settings ---
    TTS_PROVIDER: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    GCP_TTS_VOICE: Optional[str] = None
    GCP_TTS_LANGUAGE: Optional[str] = None
    TTS_CLOUD_MAX_CHARS: Optional[int] = None
    AZURE_TTS_KEY: Optional[str] = None
    AZURE_TTS_ENDPOINT: Optional[str] = None
    AZURE_TTS_DEPLOYMENT: Optional[str] = "tts"
    AZURE_TTS_VOICE: Optional[str] = None
    AZURE_TTS_API_VERSION: Optional[str] = None
    ESPEAK_VOICE: Optional[str] = None
    ESPEAK_SPEED: Optional[int] = None

    # --- LLM Settings ---
    LLM_PROVIDER: Optional[str] = None
    GEMINI_MODEL: Optional[str] = None
    LLM_TEMPERATURE: Optional[float] = None
    LLM_MAX_TOKENS: Optional[int] = None
    LLM_TIMEOUT: Optional[int] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    AZURE_OPENAI_KEY: Optional[str] = None
    AZURE_OPENAI_BASE: Optional[str] = None
    AZURE_API_VERSION: Optional[str] = None
    AZURE_DEPLOYMENT_NAME: Optional[str] = None
    OPENAI_MODEL: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None
    OLLAMA_MODEL: Optional[str] = None
    OLLAMA_BASE_URL: Optional[str] = None

    class Config:
        """
        Pydantic config subclass to specify the .env file location.
        """
        env_file = os.path.join(PROJECT_ROOT, ".env")
        env_file_encoding = 'utf-8'
        extra = "ignore" # Allow extra fields from .env to be ignored

# Instantiate the settings object that will be used throughout the application.
settings = Settings()

# --- Create Storage Directories ---
# This part of the script ensures that the necessary local storage directories
# exist when the application starts up.
def create_storage_directories():
    """
    Creates the necessary subdirectories within the main storage path.
    This helps keep uploaded files and generated artifacts organized.
    """
    # Directory for uploaded PDF files
    uploads_dir = os.path.join(settings.STORAGE_PATH, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    # Directory for generated FAISS indexes and other ML artifacts
    artifacts_dir = os.path.join(settings.STORAGE_PATH, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    
    # Directory for generated podcasts
    podcasts_dir = os.path.join(settings.STORAGE_PATH, "podcasts")
    os.makedirs(podcasts_dir, exist_ok=True)

# Run the function to ensure directories are created on import.
create_storage_directories()
