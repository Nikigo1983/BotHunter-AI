import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    logo_url: str | None
    brand_color: str | None
    display_name: str | None
    favicon_url: str | None


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=512)
    brand_color: str | None = Field(default=None, max_length=32)
    favicon_url: str | None = Field(default=None, max_length=512)


class OrganizationMemberResponse(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str
    workspace_names: list[str]
    is_active: bool
    last_login_at: datetime | None


class OrganizationMembersListResponse(BaseModel):
    items: list[OrganizationMemberResponse]


class OrganizationInviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: str = Field(default="moderator", max_length=32)
    workspace_id: uuid.UUID


class OrganizationInviteResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    workspace_id: uuid.UUID | None
    token: str
    invite_url: str
    expires_at: datetime


class OrganizationSecretItemResponse(BaseModel):
    secret_type: str
    masked_value: str
    configured: bool


class OrganizationSecretsUpdateRequest(BaseModel):
    secret_type: str = Field(max_length=64)
    value: str = Field(min_length=1)


class OrganizationSecretsListResponse(BaseModel):
    items: list[OrganizationSecretItemResponse]


class BillingMetricResponse(BaseModel):
    used: int | float
    limit: int | float
    remaining: int | float


class BillingDashboardResponse(BaseModel):
    plan: str
    ai_requests: BillingMetricResponse
    llm_tokens: BillingMetricResponse
    channels: BillingMetricResponse
    users: BillingMetricResponse
    storage_mb: BillingMetricResponse
    ai_cost_usd: BillingMetricResponse
