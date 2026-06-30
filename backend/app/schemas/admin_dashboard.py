import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.enums import AnalysisDecision, JoinRequestStatus


@dataclass(slots=True)
class JoinRequestListItemDTO:
    id: uuid.UUID
    created_at: datetime
    channel_title: str
    telegram_id: int
    username: str | None
    rule_score: float | None
    ai_score: float | None
    final_score: float | None
    decision: AnalysisDecision | None
    status: JoinRequestStatus
    is_whitelisted: bool = False
    is_blacklisted: bool = False
    trust_score: float = 50.0


@dataclass(slots=True)
class JoinRequestListResultDTO:
    items: list[JoinRequestListItemDTO]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(slots=True)
class DashboardStatisticsDTO:
    total: int
    approved: int
    rejected: int
    manual_review: int
    pending: int
    avg_rule_score: float | None
    avg_ai_score: float | None
    avg_trust_score: float | None = None


@dataclass(slots=True)
class UserInfoDTO:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    is_premium: bool
    has_photo: bool


@dataclass(slots=True)
class RuleInfoDTO:
    rule_score: float | None
    triggered_rules: list[dict[str, Any]]


@dataclass(slots=True)
class RiskProfileDTO:
    risk_level: str | None
    confidence: float | None
    signals: list[str]
    summary: str | None
    main_reason: str | None
    trust_score: float | None = None


@dataclass(slots=True)
class AIInfoDTO:
    ai_status: str | None
    ai_score: float | None
    decision: AnalysisDecision | None
    explanation: str | None
    ai_result: dict[str, Any] | None


@dataclass(slots=True)
class HistoryDTO:
    created_at: datetime
    decision_at: datetime | None
    telegram_action: str


@dataclass(slots=True)
class ManualReviewItemDTO:
    admin_action: str
    previous_decision: str
    final_decision: str
    created_at: datetime
    comment: str | None


@dataclass(slots=True)
class AIFeedbackItemDTO:
    rule_score: float | None
    ai_score: float | None
    ai_decision: str
    human_decision: str
    was_ai_correct: bool
    created_at: datetime


@dataclass(slots=True)
class ReputationHistoryItemDTO:
    created_at: datetime
    old_score: float
    new_score: float
    reason: str
    actor: str


@dataclass(slots=True)
class JoinRequestDetailDTO:
    id: uuid.UUID
    channel_title: str
    status: JoinRequestStatus
    user: UserInfoDTO
    feature_set: dict[str, Any]
    rules: RuleInfoDTO
    risk_profile: RiskProfileDTO
    ai: AIInfoDTO
    history: HistoryDTO
    rule_score: float | None = None
    ai_score: float | None = None
    final_score: float | None = None
    is_whitelisted: bool = False
    is_blacklisted: bool = False
    actions_disabled: bool = False
    manual_reviews: list[ManualReviewItemDTO] | None = None
    ai_feedbacks: list[AIFeedbackItemDTO] | None = None
    trust_score: float = 50.0
    reputation_history: list[ReputationHistoryItemDTO] | None = None
