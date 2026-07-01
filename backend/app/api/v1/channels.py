import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import require_api_dashboard_auth
from app.database.session import get_db_session
from app.schemas.channel_management import (
    ChannelDetailResponse,
    ChannelListItemResponse,
    ChannelSettingsResponse,
    ChannelSettingsUpdateRequest,
    ChannelStatisticsResponse,
)
from app.services.admin_channel import AdminChannelService

router = APIRouter(
    prefix="/admin/channels",
    tags=["admin-channels"],
    dependencies=[Depends(require_api_dashboard_auth)],
)


async def get_channel_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdminChannelService:
    return AdminChannelService(session)


def _settings_response(settings) -> ChannelSettingsResponse:
    return ChannelSettingsResponse(
        ai_enabled=settings.ai_enabled,
        rule_auto_approve=settings.rule_auto_approve,
        rule_auto_reject=settings.rule_auto_reject,
        trust_auto_approve=settings.trust_auto_approve,
        trust_auto_reject=settings.trust_auto_reject,
        join_request_timeout_hours=settings.join_request_timeout_hours,
    )


@router.get("", response_model=list[ChannelListItemResponse])
async def list_channels(
    service: AdminChannelService = Depends(get_channel_service),
) -> list[ChannelListItemResponse]:
    items = await service.list_channels()
    return [
        ChannelListItemResponse(
            id=item.id,
            title=item.title,
            telegram_chat_id=item.telegram_chat_id,
            username=item.username,
            is_active=item.is_active,
            created_at=item.created_at,
            total_requests=item.total_requests,
            approved=item.approved,
            rejected=item.rejected,
            manual_review=item.manual_review,
            avg_rule_score=item.avg_rule_score,
            avg_ai_score=item.avg_ai_score,
            avg_trust_score=item.avg_trust_score,
        )
        for item in items
    ]


@router.get("/{channel_id}", response_model=ChannelDetailResponse)
async def get_channel(
    channel_id: uuid.UUID,
    days: int = Query(default=30, ge=7, le=90),
    service: AdminChannelService = Depends(get_channel_service),
) -> ChannelDetailResponse:
    detail = await service.get_channel_detail(channel_id, timeline_days=days)
    if detail is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    stats = ChannelStatisticsResponse(
        total_requests=detail.total_requests,
        approved=detail.approved,
        rejected=detail.rejected,
        manual_review=detail.manual_review,
        pending=detail.pending,
        whitelist_count=detail.whitelist_count,
        blacklist_count=detail.blacklist_count,
        avg_rule_score=detail.avg_rule_score,
        avg_ai_score=detail.avg_ai_score,
        avg_trust_score=detail.avg_trust_score,
        ai_accuracy_percent=detail.ai_accuracy_percent,
        last_activity_at=detail.last_activity_at,
    )
    return ChannelDetailResponse(
        id=detail.id,
        title=detail.title,
        telegram_chat_id=detail.telegram_chat_id,
        username=detail.username,
        is_active=detail.is_active,
        created_at=detail.created_at,
        invite_link=detail.invite_link,
        last_activity_at=detail.last_activity_at,
        member_count=detail.member_count,
        statistics=stats,
        settings=_settings_response(detail.settings),
        recent_requests=[
            {
                "id": str(item.id),
                "created_at": item.created_at.isoformat(),
                "telegram_id": item.telegram_id,
                "username": item.username,
                "status": item.status,
                "rule_score": item.rule_score,
                "ai_score": item.ai_score,
                "final_score": item.final_score,
            }
            for item in detail.recent_requests
        ],
        timeline=[
            {
                "date": point.date,
                "total_requests": point.total_requests,
                "approved": point.approved,
                "rejected": point.rejected,
                "manual_review": point.manual_review,
                "accuracy_percent": point.accuracy_percent,
                "feedback_count": point.feedback_count,
                "ai_calls": point.ai_calls,
                "ai_cost": point.ai_cost,
            }
            for point in detail.timeline
        ],
    )


@router.get("/{channel_id}/statistics", response_model=ChannelStatisticsResponse)
async def get_channel_statistics(
    channel_id: uuid.UUID,
    service: AdminChannelService = Depends(get_channel_service),
) -> ChannelStatisticsResponse:
    stats = await service.get_statistics(channel_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ChannelStatisticsResponse(**stats)


@router.patch("/{channel_id}", response_model=ChannelDetailResponse)
async def update_channel(
    channel_id: uuid.UUID,
    payload: ChannelSettingsUpdateRequest,
    days: int = Query(default=30, ge=7, le=90),
    service: AdminChannelService = Depends(get_channel_service),
) -> ChannelDetailResponse:
    if payload.rule_auto_approve is not None and payload.rule_auto_reject is not None:
        if payload.rule_auto_reject <= payload.rule_auto_approve:
            raise HTTPException(
                status_code=422,
                detail="rule_auto_reject must be greater than rule_auto_approve",
            )
    detail = await service.update_channel(channel_id, payload)
    if detail is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return await get_channel(channel_id, days=days, service=service)
