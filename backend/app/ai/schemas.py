from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


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
    recommended_action: str = Field(min_length=1, max_length=300)
    positive_signals: list[str] = Field(default_factory=list, max_length=10)
    negative_signals: list[str] = Field(default_factory=list, max_length=10)
    short_summary: str = Field(default="", max_length=200)
    signals: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def normalize_signals(self) -> "StructuredAnalysisOutput":
        if self.signals and not self.positive_signals and not self.negative_signals:
            object.__setattr__(self, "negative_signals", list(self.signals))
        return self


def structured_output_json_schema() -> dict[str, Any]:
    schema = StructuredAnalysisOutput.model_json_schema()
    properties = dict(schema.get("properties", {}))
    if "ai_score" in properties:
        properties["risk_score"] = properties.pop("ai_score")
    for deprecated in ("signals",):
        properties.pop(deprecated, None)
    schema["properties"] = properties
    required = [
        "risk_score" if field == "ai_score" else field
        for field in schema.get("required", [])
        if field not in {"signals", "short_summary", "positive_signals", "negative_signals"}
    ]
    required.extend(
        field
        for field in (
            "positive_signals",
            "negative_signals",
            "short_summary",
            "recommended_action",
        )
        if field not in required
    )
    schema["required"] = required
    schema["additionalProperties"] = False
    return schema
