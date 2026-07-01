import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


@dataclass(slots=True)
class ChannelListItemDTO:
    id: uuid.UUID
    title: str
    telegram_chat_id: int
    username: str | None
    is_active: bool
    created_at: datetime
    total_requests: int
    approved: int
    rejected: int
    manual_review: int
    avg_rule_score: float | None
    avg_ai_score: float | None
    avg_trust_score: float | None


@dataclass(slots=True)
class ChannelSettingsDTO:
    ai_enabled: bool
    rule_auto_approve: int
    rule_auto_reject: int
    trust_auto_approve: int
    trust_auto_reject: int
    join_request_timeout_hours: int | None


@dataclass(slots=True)
class ChannelRecentRequestDTO:
    id: uuid.UUID
    created_at: datetime
    telegram_id: int
    username: str | None
    status: str
    rule_score: float | None
    ai_score: float | None
    final_score: float | None


@dataclass(slots=True)
class ChannelTimelinePointDTO:
    date: str
    total_requests: int
    approved: int
    rejected: int
    manual_review: int
    accuracy_percent: float | None
    feedback_count: int
    ai_calls: int
    ai_cost: float


@dataclass(slots=True)
class ChannelDetailDTO:
    id: uuid.UUID
    title: str
    telegram_chat_id: int
    username: str | None
    is_active: bool
    created_at: datetime
    invite_link: str | None
    last_activity_at: datetime | None
    member_count: int | None
    total_requests: int
    approved: int
    rejected: int
    manual_review: int
    pending: int
    whitelist_count: int
    blacklist_count: int
    avg_rule_score: float | None
    avg_ai_score: float | None
    avg_trust_score: float | None
    ai_accuracy_percent: float | None
    settings: ChannelSettingsDTO
    recent_requests: list[ChannelRecentRequestDTO]
    timeline: list[ChannelTimelinePointDTO]


class ChannelSettingsUpdateRequest(BaseModel):
    ai_enabled: bool | None = None
    rule_auto_approve: int | None = Field(default=None, ge=0, le=100)
    rule_auto_reject: int | None = Field(default=None, ge=0, le=100)
    trust_auto_approve: int | None = Field(default=None, ge=0, le=100)
    trust_auto_reject: int | None = Field(default=None, ge=0, le=100)
    join_request_timeout_hours: int | None = Field(default=None, ge=1, le=720)
    is_active: bool | None = None


class ChannelSettingsResponse(BaseModel):
    ai_enabled: bool
    rule_auto_approve: int
    rule_auto_reject: int
    trust_auto_approve: int
    trust_auto_reject: int
    join_request_timeout_hours: int | None


class ChannelListItemResponse(BaseModel):
    id: uuid.UUID
    title: str
    telegram_chat_id: int
    username: str | None
    is_active: bool
    created_at: datetime
    total_requests: int
    approved: int
    rejected: int
    manual_review: int
    avg_rule_score: float | None
    avg_ai_score: float | None
    avg_trust_score: float | None


class ChannelStatisticsResponse(BaseModel):
    total_requests: int
    approved: int
    rejected: int
    manual_review: int
    pending: int
    whitelist_count: int
    blacklist_count: int
    avg_rule_score: float | None
    avg_ai_score: float | None
    avg_trust_score: float | None
    ai_accuracy_percent: float | None
    last_activity_at: datetime | None


class ChannelDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    telegram_chat_id: int
    username: str | None
    is_active: bool
    created_at: datetime
    invite_link: str | None
    last_activity_at: datetime | None
    member_count: int | None
    statistics: ChannelStatisticsResponse
    settings: ChannelSettingsResponse
    recent_requests: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
