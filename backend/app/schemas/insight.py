from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum # Import Enum
import json # Ensure json is imported at the top level

# Define an Enum for insight types
class InsightType(str, Enum):
    KEY_INSIGHTS = "Key insights"
    DID_YOU_KNOW = "Did you know?"
    CONTRADICTIONS_COUNTERPOINTS = "Contradictions / counterpoints"
    INSPIRATIONS_CONNECTIONS = "Inspirations or connections across docs"
    GENERATION_ERROR = "generation_error" # For fallback

# Define the structure for individual insight items
class InsightItem(BaseModel):
    """
    Pydantic model for a single structured insight item.
    """
    type: InsightType = Field(..., description="The category of the insight.")
    data: str = Field(..., description="The actual text content of the structured insight.")
    priority: int = Field(1, description="A numerical priority for the insight, lower is higher priority.")

# --- Request Model for Generation ---
# This model is for the API endpoint that triggers insight generation.
class InsightGenerateRequest(BaseModel):
    """
    Pydantic model for the request body to generate insights.
    """
    # No specific fields needed here as the IDs will be path/query parameters
    pass

# --- Response Model ---
# This model represents the full insight data sent back to the client.
class InsightInDB(BaseModel):
    """
    Pydantic model representing an insight as stored in the database.
    
    This model is used for API responses.
    """
    insightId: str = Field(..., description="The unique identifier for the insight.")
    sourceType: str = Field(..., description="The type of the source ('document', 'collection', or 'recommendation').")
    sourceId: str = Field(..., description="The ID of the source entity.")
    insights_data: List[InsightItem] = Field(..., description="The list of structured insight items.")
    generatedAt: datetime = Field(..., description="The timestamp when the insight was generated.")
    
    @field_validator('insights_data', mode='before')
    @classmethod
    def parse_insights_data(cls, v: Any) -> List[InsightItem]:
        """
        If the input is a string (from JSON column), attempt to parse it as JSON.
        """
        if isinstance(v, str):
            try:
                parsed_json = json.loads(v)
                if isinstance(parsed_json, list):
                    return [InsightItem(**item) for item in parsed_json]
                else:
                    raise ValueError("Parsed JSON is not a list.")
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"Invalid insights_data JSON: {e}") from e
        elif isinstance(v, list):
            return [InsightItem(**item) if isinstance(item, dict) else item for item in v]
        return v

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "insightId": "insight_abc123",
                "sourceType": "document",
                "sourceId": "doc_xyz789",
                "insights_data": [
                    {"type": "key_insight", "data": "The main point of the document is...", "priority": 1},
                    {"type": "did_you_know", "data": "Did you know that...", "priority": 2}
                ],
                "generatedAt": "2025-01-01T12:00:00"
            }
        }
    )
