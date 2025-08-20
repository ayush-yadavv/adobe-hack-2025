from pydantic import BaseModel, Field, computed_field, model_validator
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum
import json

from .recommendation_item import RecommendationItemSchema

class RecommendationType(str, Enum):
    PERSONA = "persona"
    TEXT = "text"

class SnippetRequest(BaseModel):
    selected_text: str = Field(..., description="The text selected by the user in the document.")
    current_doc_id: str = Field(..., description="The ID of the document the user is currently viewing.")
    collection_id: str = Field(..., description="The ID of the collection being viewed.")
    spanned_section_ids: List[str] = Field(..., description="The IDs of the structural sections the selection spans.")

class Snippet(BaseModel):
    document_name: str = Field(..., alias="document")
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    content: str
    snippet_explanation: Optional[str] = None
    collection_id: str
    _distance: float

    class Config:
        populate_by_name = True
        from_attributes = True

class Insight(BaseModel):
    type: str
    text: str

class SnippetResponse(BaseModel):
    recommendations: List[Snippet]
    insights: List[Insight] = []

class RecommendationSchema(BaseModel):
    """
    Pydantic schema for the Recommendation model.
    """
    recommendation_id: str
    collection_id: str
    user_selection_text: Optional[str] = None
    latest_podcast_id: Optional[str] = None
    latest_insight_id: Optional[str] = None
    generated_at: datetime
    recommendation_type: RecommendationType = Field(..., description="Type of recommendation: persona or text")
    items: List[RecommendationItemSchema] = []
    
    # @computed_field
    # @property
    # def spanned_section_ids(self) -> List[str]:
    #     if self.spanned_section_ids_raw:
    #         try:
    #             return json.loads(self.spanned_section_ids_raw)
    #         except json.JSONDecodeError:
    #             pass
    #     return []

    # @computed_field
    # @property
    # def list_of_doc_ids_used(self) -> List[str]:
    #     if self.list_of_doc_ids_used_raw:
    #         try:
    #             return json.loads(self.list_of_doc_ids_used_raw)
    #         except json.JSONDecodeError:
    #             pass
    #     return []
    @model_validator(mode='after')
    def check_insight_id(self) -> 'RecommendationSchema':
        print(f"DEBUG: RecommendationSchema: latest_insight_id during validation: {self.latest_insight_id}")
        return self

    class Config:
        from_attributes = True
