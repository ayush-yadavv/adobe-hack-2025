from pydantic import BaseModel, Field, ConfigDict # Import ConfigDict
from typing import Optional

class DocumentOutlineItemPydantic(BaseModel):
    """
    Pydantic model for a single item in a document's outline, for API responses.
    """
    level: str = Field(..., description="The heading level (e.g., 'H1', 'H2').")
    section_id: str = Field(..., description="The unique identifier for this section.")
    documentId: str = Field(..., description="The ID of the document this outline item belongs to.")
    text: str = Field(..., description="The text content of the heading.")
    annotation: Optional[str] = Field(None, description="Additional annotation data.")
    page: int = Field(..., description="The page number where the section appears.")

    model_config = ConfigDict(
        from_attributes=True
    )
