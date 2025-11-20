import os
import uuid
from pathlib import Path
from fastapi import UploadFile
import shutil
import logging

from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StorageService:
    """
    A service class to handle file storage operations.
    
    This class provides an abstraction layer for file storage. Initially, it
    implements local file storage, but it can be extended to support cloud
    storage providers like S3 by changing the implementation of these methods
    without affecting the rest of the application.
    """

    def __init__(self, base_path: str = settings.STORAGE_PATH):
        """
        Initializes the StorageService.
        
        Args:
            base_path: The root directory for all storage operations.
                       Defaults to the path specified in the application settings.
        """
        self.base_path = Path(base_path)
        self.uploads_dir = self.base_path / "uploads"
        self.artifacts_dir = self.base_path / "artifacts"
        self.podcasts_dir = self.base_path / "podcasts"
        
        # Ensure the directories exist
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.podcasts_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Storage initialized at base path: {self.base_path}")

    def save_uploaded_file(self, file: UploadFile, collection_id: str) -> str:
        """
        Saves an uploaded file to a structured directory path.

        Args:
            file: The uploaded file object from FastAPI.
            collection_id: The ID of the collection to associate the file with.

        Returns:
            The relative path to the saved file as a string (relative to storage base).
        """
        try:
            # Sanitize filename to prevent directory traversal attacks
            if file.filename is None:
                raise ValueError("Uploaded file must have a filename.")
                
            safe_filename = Path(file.filename).name
            logger.debug(f"Original filename: {file.filename}, safe_filename: {safe_filename}")
            
            # Create a unique identifier to prevent filename collisions
            unique_id = uuid.uuid4().hex
            unique_filename = f"{unique_id}_{safe_filename}"
            logger.debug(f"Generated unique filename: {unique_filename}")
            
            # Organize uploads by collection
            collection_dir = self.uploads_dir / collection_id
            logger.debug(f"Collection directory path: {collection_dir}")
            
            # Ensure the directory exists
            collection_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Directory exists after creation: {collection_dir.exists()}")
            
            file_path = collection_dir / unique_filename
            logger.debug(f"Full file path: {file_path}")
            
            # Log before attempting to save
            logger.info(f"Attempting to save file to: {file_path}")
            
            # Save the file
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Verify the file was saved
            if not file_path.exists() or file_path.stat().st_size == 0:
                error_msg = f"Failed to save file: {file_path} (file doesn't exist or is empty)"
                logger.error(error_msg)
                raise IOError(error_msg)
                
            logger.info(f"Successfully saved uploaded file to: {file_path}")
            logger.info(f"File size: {file_path.stat().st_size} bytes")
            
            # Get relative path for storage
            relative_path = str(file_path.relative_to(self.base_path))
            logger.info(f"Relative path for storage: {relative_path}")
            
            return relative_path
            
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}", exc_info=True)
            raise
            
        finally:
            # Ensure the file is properly closed
            if hasattr(file, 'file') and hasattr(file.file, 'close'):
                file.file.close()

    def get_file_url(self, relative_path: str) -> str:
        """
        Generates a full accessible URL for a stored file.

        Args:
            relative_path: The relative path of the file (from storage base)

        Returns:
            Full URL accessible via the web server
        """
        try:
            # Ensure the relative path is a string and normalize path separators
            if not isinstance(relative_path, str):
                raise ValueError(f"Relative path must be a string, got {type(relative_path)}")
                
            # Convert Windows path separators to forward slashes and normalize
            url_path = str(relative_path).replace('\\', '/').replace('//', '/')
            
            # Ensure the path doesn't start with a slash to avoid double slashes
            if url_path.startswith('/'):
                url_path = url_path[1:]
            
            # If the relative path starts with 'storage/', remove it as we add it in the full URL
            if url_path.startswith('storage/'):
                url_path = url_path[8:]
                
            # Ensure the base URL doesn't end with a slash
            base_url = settings.BASE_URL.rstrip('/')
            
            # Fix for missing port in BASE_URL if it's just http://localhost
            if base_url == "http://localhost":
                base_url = "http://localhost:8000"
            
            # Construct the full URL
            full_url = f"{base_url}/storage/{url_path}"
            
            logger.debug(f"Generated file URL for {relative_path} -> {full_url}")
            return full_url
            
        except Exception as e:
            logger.error(f"Error generating file URL for {relative_path}: {str(e)}", exc_info=True)
            raise

    def get_absolute_path(self, relative_path: str) -> Path:
        """
        Gets the absolute filesystem path for a relative storage path.

        Args:
            relative_path: The relative path of the file (from storage base)

        Returns:
            Absolute Path object

        Raises:
            ValueError: If the relative path is invalid or tries to access outside the base directory
            FileNotFoundError: If the resulting path doesn't exist
        """
        try:
            if not relative_path:
                raise ValueError("Relative path cannot be empty")
                
            # Convert to string in case a Path object is passed
            rel_path_str = str(relative_path)
            
            # Normalize the path to prevent directory traversal
            normalized_path = (self.base_path / rel_path_str).resolve()
            
            # Ensure the path is within the base directory for security
            try:
                normalized_path.relative_to(self.base_path.resolve())
            except ValueError:
                raise ValueError(f"Path '{rel_path_str}' is outside the base directory")
            
            # Check if the file exists
            if not normalized_path.exists():
                raise FileNotFoundError(f"File not found: {normalized_path}")
                
            logger.debug(f"Resolved absolute path for '{rel_path_str}' -> {normalized_path}")
            return normalized_path
            
        except Exception as e:
            logger.error(f"Error resolving absolute path for '{relative_path}': {str(e)}", exc_info=True)
            raise

    def save_artifact(self, data: bytes, artifact_name: str) -> str:
        """
        Saves a binary artifact (like a FAISS index) to the artifacts directory.

        Args:
            data: The binary data to save.
            artifact_name: The name of the artifact file.

        Returns:
            The path to the saved artifact as a string.
        """
        file_path = self.artifacts_dir / artifact_name
        with file_path.open("wb") as f:
            f.write(data)
        logger.info(f"Saved artifact to: {file_path}")
        return str(file_path)

    def get_artifact_path(self, artifact_name: str) -> Path:
        """
        Gets the full Path object for a given artifact name.

        Args:
            artifact_name: The name of the artifact file.

        Returns:
            A Path object pointing to the artifact.
        """
        return self.artifacts_dir / artifact_name

    def get_podcast_path(self, podcast_filename: str) -> Path:
        """
        Gets the full Path object for a given podcast filename.

        Args:
            podcast_filename: The name of the podcast file.

        Returns:
            A Path object pointing to the podcast file.
        """
        return self.podcasts_dir / podcast_filename

    def delete_uploaded_file(self, relative_path: str):
        """
        Deletes an uploaded file from the storage.

        Args:
            relative_path: The relative path of the file (from storage base)
        """
        file_path = self.base_path / relative_path
        if file_path.exists() and file_path.is_file():
            try:
                os.remove(file_path)
                logger.info(f"Deleted uploaded file: {file_path}")
            except OSError as e:
                logger.error(f"Error deleting uploaded file {file_path}: {e}")
                raise RuntimeError(f"Could not delete uploaded file: {e}")
        else:
            logger.warning(f"Attempted to delete non-existent uploaded file: {file_path}")

    def delete_collection_directory(self, collection_id: str):
        """
        Deletes a collection directory and all its contents from storage.

        Args:
            collection_id: The ID of the collection to delete
        """
        collection_dir = self.uploads_dir / collection_id
        logger.debug(f"Attempting to delete collection directory at: {collection_dir.absolute()}")
        
        if collection_dir.exists() and collection_dir.is_dir():
            try:
                shutil.rmtree(collection_dir)
                logger.info(f"Successfully deleted collection directory: {collection_dir}")
            except OSError as e:
                logger.error(f"Error deleting collection directory {collection_dir}: {e}", exc_info=True)
                raise RuntimeError(f"Could not delete collection directory: {e}")
        else:
            logger.warning(f"Collection directory does not exist: {collection_dir}")

    def delete_podcast_file(self, podcast_filename: str):
        """
        Deletes a podcast audio file from the storage.

        Args:
            podcast_filename: The name of the podcast file to delete.
        """
        file_path = self.podcasts_dir / podcast_filename
        if file_path.exists() and file_path.is_file():
            try:
                os.remove(file_path)
                logger.info(f"Deleted podcast file: {file_path}")
            except OSError as e:
                logger.error(f"Error deleting podcast file {file_path}: {e}")
                raise RuntimeError(f"Could not delete podcast file: {e}")
        else:
            logger.warning(f"Attempted to delete non-existent podcast file: {file_path}")


# Create a single instance of the service to be used as a dependency
storage_service = StorageService()

def get_storage_service():
    """
    Dependency function to provide the storage service instance.
    """
    return storage_service
