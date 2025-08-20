from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime
import json

class RecommendationItemSchema(BaseModel):
    """
    Pydantic schema for the RecommendationItem model.
    """
    item_id: str
    recommendation_id: str
    document_title: Optional[str] = None # Renamed from document_name
    doc_id: str
    section_title: Optional[str] = None
    section_id: str
    page_number: Optional[int] = None
    snippet_text: str
    snippet_explanation: Optional[str] = None
    annotation: Optional[str] = None # Assuming annotation is stored as a string (e.g., JSON string)
    quad_points: Optional[List[List[float]]] = None

    @field_validator('quad_points', mode='before')
    @classmethod
    def parse_quad_points(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                pass # Let Pydantic handle validation if it's not valid JSON
        return v

    class Config:
        from_attributes = True # Use from_attributes for Pydantic v2+
