import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AnalysisDecision


@dataclass(slots=True)
class AIAccuracyDTO:
    total_decisions: int
    matched: int
    mismatched: int
    accuracy_percent: float | None
    false_approve: int
    false_reject: int
    manual_review_accuracy_percent: float | None


@dataclass(slots=True)
class DecisionDistributionItemDTO:
    decision: str
    count: int


@dataclass(slots=True)
class ProviderStatDTO:
    provider: str
    model: str
    requests: int
    avg_latency_ms: float
    avg_tokens: float
    avg_cost: float
    avg_confidence: float | None
    accuracy_percent: float | None


@dataclass(slots=True)
class RuleEffectivenessDTO:
    rule_name: str
    triggered_count: int
    avg_rule_score: float
    ai_agreed_count: int
    admin_agreed_count: int
    false_positive_count: int


@dataclass(slots=True)
class FeedbackCategoryDTO:
    category: str
    label: str
    count: int


@dataclass(slots=True)
class FeedbackCaseDTO:
    id: uuid.UUID
    join_request_id: uuid.UUID
    created_at: datetime
    ai_decision: str
    human_decision: str
    was_ai_correct: bool
    category: str


@dataclass(slots=True)
class TimelinePointDTO:
    date: str
    accuracy_percent: float | None
    avg_cost: float
    avg_latency_ms: float
    avg_confidence: float | None
    feedback_count: int
    usage_count: int


@dataclass(slots=True)
class UsageDashboardDTO:
    total_cost: float
    today_cost: float
    month_cost: float
    avg_tokens: float
    avg_latency_ms: float
    most_used_model: str | None
    most_accurate_model: str | None
    most_expensive_model: str | None


@dataclass(slots=True)
class AnalyticsOverviewDTO:
    accuracy: AIAccuracyDTO
    decision_distribution: list[DecisionDistributionItemDTO]
    providers: list[ProviderStatDTO]
    rules: list[RuleEffectivenessDTO]
    feedback_categories: list[FeedbackCategoryDTO]
    recent_feedback: list[FeedbackCaseDTO]
    usage: UsageDashboardDTO


@dataclass(slots=True)
class DecisionComparisonDTO:
    ai_decision: str | None
    human_decision: str | None
    was_ai_correct: bool | None
    has_override: bool
    verdict: str | None
    verdict_class: str | None


class AIAccuracyResponse(BaseModel):
    total_decisions: int
    matched: int
    mismatched: int
    accuracy_percent: float | None
    false_approve: int
    false_reject: int
    manual_review_accuracy_percent: float | None


class DecisionDistributionItemResponse(BaseModel):
    decision: str
    count: int


class ProviderStatResponse(BaseModel):
    provider: str
    model: str
    requests: int
    avg_latency_ms: float
    avg_tokens: float
    avg_cost: float
    avg_confidence: float | None
    accuracy_percent: float | None


class RuleEffectivenessResponse(BaseModel):
    rule_name: str
    triggered_count: int
    avg_rule_score: float
    ai_agreed_count: int
    admin_agreed_count: int
    false_positive_count: int


class FeedbackCategoryResponse(BaseModel):
    category: str
    label: str
    count: int


class FeedbackCaseResponse(BaseModel):
    id: uuid.UUID
    join_request_id: uuid.UUID
    created_at: datetime
    ai_decision: str
    human_decision: str
    was_ai_correct: bool
    category: str


class TimelinePointResponse(BaseModel):
    date: str
    accuracy_percent: float | None
    avg_cost: float
    avg_latency_ms: float
    avg_confidence: float | None
    feedback_count: int
    usage_count: int


class UsageDashboardResponse(BaseModel):
    total_cost: float
    today_cost: float
    month_cost: float
    avg_tokens: float
    avg_latency_ms: float
    most_used_model: str | None
    most_accurate_model: str | None
    most_expensive_model: str | None


class AnalyticsOverviewResponse(BaseModel):
    accuracy: AIAccuracyResponse
    decision_distribution: list[DecisionDistributionItemResponse]
    providers: list[ProviderStatResponse]
    rules: list[RuleEffectivenessResponse]
    feedback_categories: list[FeedbackCategoryResponse]
    recent_feedback: list[FeedbackCaseResponse]
    usage: UsageDashboardResponse

