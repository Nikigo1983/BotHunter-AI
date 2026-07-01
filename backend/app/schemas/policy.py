import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RulePolicyResponse(BaseModel):
    rule_key: str
    name: str
    description: str
    score: int
    enabled: bool
    triggered_count: int
    accuracy: float | None
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    false_positive_rate: float | None
    false_negative_rate: float | None
    last_changed_at: datetime | None
    last_changed_by: str | None
    admin_comment: str | None


class RulePolicyListResponse(BaseModel):
    items: list[RulePolicyResponse]
    version_number: int
    version_id: uuid.UUID | None


class RulePolicyUpdateRequest(BaseModel):
    score: int = Field(ge=0, le=100)
    enabled: bool
    description: str = Field(min_length=1, max_length=500)
    admin_comment: str | None = Field(default=None, max_length=2000)


class PolicyThresholdResponse(BaseModel):
    approve_below: int
    reject_from: int
    trust_auto_approve: int
    trust_auto_reject: int
    ai_threshold: float


class PolicyThresholdUpdateRequest(BaseModel):
    approve_below: int = Field(ge=0, le=100)
    reject_from: int = Field(ge=0, le=100)
    trust_auto_approve: int = Field(ge=0, le=100)
    trust_auto_reject: int = Field(ge=0, le=100)
    ai_threshold: float = Field(ge=0.0, le=1.0)
    comment: str | None = Field(default=None, max_length=2000)


class SimulationDecisionDeltaResponse(BaseModel):
    approved: int
    rejected: int
    manual_review: int


class PolicySimulationRequest(BaseModel):
    rule_key: str | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    enabled: bool | None = None
    thresholds: PolicyThresholdUpdateRequest | None = None
    sample_size: int = Field(default=100, ge=1, le=500)


class PolicySimulationResponse(BaseModel):
    sample_size: int
    baseline: SimulationDecisionDeltaResponse
    simulated: SimulationDecisionDeltaResponse
    delta: SimulationDecisionDeltaResponse


class PolicyVersionResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    author: str
    comment: str | None
    created_at: datetime
    is_current: bool
    changed_rules: list[str]


class PolicyHistoryResponse(BaseModel):
    items: list[PolicyVersionResponse]


class PolicyRollbackRequest(BaseModel):
    version_id: uuid.UUID


class PolicyComparisonResponse(BaseModel):
    current_version: int
    previous_version: int
    rule_changes: list[dict]
    threshold_changes: list[dict]
