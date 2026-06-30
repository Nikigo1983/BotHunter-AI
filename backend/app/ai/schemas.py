from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class StructuredAnalysisOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ai_score: int = Field(
        ge=0,
        le=100,
        validation_alias=AliasChoices("ai_score", "risk_score"),
        serialization_alias="risk_score",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    decision: Literal["Approved", "ManualReview", "Rejected"]
    reason: str = Field(min_length=1, max_length=500)
    recommended_action: Literal["Approve", "ManualReview", "Reject"] = "ManualReview"
    signals: list[str] = Field(default_factory=list)


def structured_output_json_schema() -> dict[str, Any]:
    schema = StructuredAnalysisOutput.model_json_schema()
    properties = dict(schema.get("properties", {}))
    if "ai_score" in properties:
        properties["risk_score"] = properties.pop("ai_score")
    schema["properties"] = properties
    required = [
        "risk_score" if field == "ai_score" else field
        for field in schema.get("required", [])
    ]
    schema["required"] = required
    schema["additionalProperties"] = False
    return schema
