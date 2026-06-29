from typing import Literal

from pydantic import BaseModel, Field


class StructuredAnalysisOutput(BaseModel):
    ai_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    decision: Literal["Approved", "ManualReview", "Rejected"]
    reason: str = Field(min_length=1, max_length=500)
