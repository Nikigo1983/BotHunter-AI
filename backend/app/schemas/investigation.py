import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.schemas.admin_dashboard import JoinRequestDetailDTO


@dataclass(slots=True)
class InvestigationListItemDTO:
    id: uuid.UUID
    created_at: datetime
    channel_id: uuid.UUID
    channel_title: str
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    status: JoinRequestStatus
    rule_score: float | None
    ai_score: float | None
    final_score: float | None
    ai_decision: str | None
    human_decision: str | None
    trust_score: float


@dataclass(slots=True)
class InvestigationListResultDTO:
    items: list[InvestigationListItemDTO]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(slots=True)
class TimelineEventDTO:
    stage: str
    title: str
    timestamp: datetime | None
    duration_ms: int | None
    result: str | None
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class PromptViewDTO:
    system_prompt: str
    user_prompt: str


@dataclass(slots=True)
class AIResponseViewDTO:
    parsed_response: dict[str, Any] | None
    raw_json: str | None
    ai_status: str | None


@dataclass(slots=True)
class RuleInspectionItemDTO:
    rule: str
    condition: str
    description: str
    matched: bool
    contribution: int


@dataclass(slots=True)
class DecisionFlowDTO:
    rule_engine_decision: str | None
    ai_decision: str | None
    final_decision: str | None
    human_decision: str | None
    ai_matches_human: bool | None
    verdict: str | None
    verdict_class: str | None


@dataclass(slots=True)
class AuditLogItemDTO:
    id: uuid.UUID
    created_at: datetime
    actor: str
    action: str
    details: str | None


@dataclass(slots=True)
class InvestigationDetailDTO:
    case: JoinRequestDetailDTO
    channel_id: uuid.UUID
    timeline: list[TimelineEventDTO]
    prompt: PromptViewDTO | None
    ai_response: AIResponseViewDTO
    rule_inspection: list[RuleInspectionItemDTO]
    decision_flow: DecisionFlowDTO
    audit_logs: list[AuditLogItemDTO]


@dataclass(slots=True)
class ReplayResultDTO:
    rule_score: int
    rule_engine_decision: str
    ai_status: str
    ai_decision: str | None
    ai_score: int | None
    final_decision: str
    prompt: PromptViewDTO
    ai_response: dict[str, Any] | None
    triggered_rules: list[dict[str, Any]]


class InvestigationFiltersRequest(BaseModel):
    channel_id: uuid.UUID | None = None
    status: str = "all"
    ai_decision: AnalysisDecision | None = None
    human_decision: AnalysisDecision | None = None
    trust_min: float | None = Field(default=None, ge=0, le=100)
    trust_max: float | None = Field(default=None, ge=0, le=100)
    rule_min: float | None = Field(default=None, ge=0, le=100)
    rule_max: float | None = Field(default=None, ge=0, le=100)
    ai_min: float | None = Field(default=None, ge=0, le=100)
    ai_max: float | None = Field(default=None, ge=0, le=100)
    date_from: datetime | None = None
    date_to: datetime | None = None
    search: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class InvestigationListItemResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    channel_id: uuid.UUID
    channel_title: str
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    status: str
    rule_score: float | None
    ai_score: float | None
    final_score: float | None
    ai_decision: str | None
    human_decision: str | None
    trust_score: float


class InvestigationListResponse(BaseModel):
    items: list[InvestigationListItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TimelineEventResponse(BaseModel):
    stage: str
    title: str
    timestamp: datetime | None
    duration_ms: int | None
    result: str | None
    details: dict[str, Any] | None = None


class InvestigationDetailResponse(BaseModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    channel_title: str
    status: str
    timeline: list[TimelineEventResponse]
    prompt: dict[str, str] | None
    ai_response: dict[str, Any]
    rule_inspection: list[dict[str, Any]]
    decision_flow: dict[str, Any]
    audit_logs: list[dict[str, Any]]
    case: dict[str, Any]


class ReplayResponse(BaseModel):
    rule_score: int
    rule_engine_decision: str
    ai_status: str
    ai_decision: str | None
    ai_score: int | None
    final_decision: str
    prompt: dict[str, str]
    ai_response: dict[str, Any] | None
    triggered_rules: list[dict[str, Any]]
