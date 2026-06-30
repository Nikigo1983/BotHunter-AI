import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JoinRequestListItemResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    channel_title: str
    telegram_id: int
    username: str | None
    rule_score: float | None
    ai_score: float | None
    final_score: float | None
    decision: str | None
    status: str


class JoinRequestListResponse(BaseModel):
    items: list[JoinRequestListItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DashboardStatisticsResponse(BaseModel):
    total: int
    approved: int
    rejected: int
    manual_review: int
    pending: int
    avg_rule_score: float | None
    avg_ai_score: float | None


class UserInfoResponse(BaseModel):
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    is_premium: bool
    has_photo: bool


class RuleInfoResponse(BaseModel):
    rule_score: float | None
    triggered_rules: list[dict[str, Any]]


class RiskProfileResponse(BaseModel):
    risk_level: str | None
    confidence: float | None
    signals: list[str]
    summary: str | None
    main_reason: str | None


class AIInfoResponse(BaseModel):
    ai_status: str | None
    ai_score: float | None
    decision: str | None
    explanation: str | None
    ai_result: dict[str, Any] | None


class HistoryResponse(BaseModel):
    created_at: datetime
    decision_at: datetime | None
    telegram_action: str


class JoinRequestDetailResponse(BaseModel):
    id: uuid.UUID
    channel_title: str
    status: str
    user: UserInfoResponse
    feature_set: dict[str, Any]
    rules: RuleInfoResponse
    risk_profile: RiskProfileResponse
    ai: AIInfoResponse
    history: HistoryResponse


class ActionResponse(BaseModel):
    success: bool = True
    message: str
    error: str | None = None
