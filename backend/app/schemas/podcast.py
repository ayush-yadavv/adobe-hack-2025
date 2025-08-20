from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# --- Request Model for Generation ---
class PodcastGenerateRequest(BaseModel):
    """
    Pydantic model for the request body to generate a podcast.
    """
    include_insights: bool = Field(False, description="Flag to include insights in the podcast summary.")
    min_duration_seconds: Optional[int] = Field(120, description="Minimum desired podcast duration in seconds (default: 120s = 2min).")
    max_duration_seconds: Optional[int] = Field(240, description="Maximum desired podcast duration in seconds (default: 240s = 4min).")

# --- New Models for LLM Structured Output ---
class PodcastSegment(BaseModel):
    """
    Represents a single segment of the podcast script.
    """
    speaker: str = Field(..., description="The speaker for this segment (e.g., 'HOST', 'GUEST').")
    dialogue: str = Field(..., description="The dialogue for this segment.")
    words: int = Field(..., description="The estimated word count for this segment.")
    order: int = Field(..., description="The order of this segment in the overall script.")

class PodcastScriptResponse(BaseModel):
    """
    Represents the structured output from the LLM for the podcast script and short description.
    """
    script: List[PodcastSegment] = Field(..., description="A list of podcast segments in order.")
    short_description: str = Field(..., description="A two-sentence description of what the podcast is all about.")


# --- Base Model ---
class PodcastBase(BaseModel):
    """
    Base Pydantic model for a podcast.
    """
    sourceType: str = Field(..., description="The type of the source ('document' or 'recommendation').")
    sourceId: str = Field(..., description="The ID of the source entity.")
    transcript: Optional[List[PodcastSegment]] = Field(None, description="A list of podcast segments, representing the full transcript.")

# --- Create Model ---
class PodcastCreate(PodcastBase):
    """
    Pydantic model for creating a new podcast record in the database.
    """
    pass

# --- Response Model ---
class PodcastInDB(PodcastBase):
    """
    Pydantic model representing a podcast as stored in the database.
    This model is used for API responses.
    """
    podcastId: str = Field(..., description="The unique identifier for the podcast.")
    status: str = Field(..., description="The current status of the generation job.")
    audioUrl: Optional[str] = Field(None, description="The URL where the generated audio file is stored.")
    durationSeconds: Optional[int] = Field(None, description="The length of the audio in seconds.")
    generatedAt: datetime = Field(..., description="The timestamp when the podcast was generated.")
    shortDescription: Optional[str] = Field(None, description="A two-sentence description of what the podcast is all about.")

    class Config:
        from_attributes = True
