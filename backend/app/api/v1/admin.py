import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.repositories.admin_dashboard import StatusFilter
from app.schemas.admin_api import (
    ActionResponse,
    AIInfoResponse,
    DashboardStatisticsResponse,
    HistoryResponse,
    JoinRequestDetailResponse,
    JoinRequestListItemResponse,
    JoinRequestListResponse,
    RiskProfileResponse,
    RuleInfoResponse,
    UserInfoResponse,
)
from app.services.admin_dashboard import AdminDashboardService, PAGE_SIZE
from app.services.admin_join_request_action import AdminJoinRequestActionService

router = APIRouter(prefix="/admin", tags=["admin"])


async def get_admin_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdminDashboardService:
    return AdminDashboardService(session)


async def get_action_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdminJoinRequestActionService:
    return AdminJoinRequestActionService(session)


@router.get("/join-requests", response_model=JoinRequestListResponse)
async def list_join_requests(
    status: StatusFilter = Query(default="all"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=PAGE_SIZE, ge=1, le=100),
    service: AdminDashboardService = Depends(get_admin_service),
) -> JoinRequestListResponse:
    result = await service.list_join_requests(
        status_filter=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    return JoinRequestListResponse(
        items=[
            JoinRequestListItemResponse(
                id=item.id,
                created_at=item.created_at,
                channel_title=item.channel_title,
                telegram_id=item.telegram_id,
                username=item.username,
                rule_score=item.rule_score,
                ai_score=item.ai_score,
                final_score=item.final_score,
                decision=item.decision.value if item.decision else None,
                status=item.status.value,
            )
            for item in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.get("/join-requests/{join_request_id}", response_model=JoinRequestDetailResponse)
async def get_join_request_detail(
    join_request_id: uuid.UUID,
    service: AdminDashboardService = Depends(get_admin_service),
) -> JoinRequestDetailResponse:
    detail = await service.get_join_request_detail(join_request_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Join request not found")
    return JoinRequestDetailResponse(
        id=detail.id,
        channel_title=detail.channel_title,
        status=detail.status.value,
        user=UserInfoResponse(
            telegram_id=detail.user.telegram_id,
            username=detail.user.username,
            first_name=detail.user.first_name,
            last_name=detail.user.last_name,
            language_code=detail.user.language_code,
            is_premium=detail.user.is_premium,
            has_photo=detail.user.has_photo,
        ),
        feature_set=detail.feature_set,
        rules=RuleInfoResponse(
            rule_score=detail.rules.rule_score,
            triggered_rules=detail.rules.triggered_rules,
        ),
        risk_profile=RiskProfileResponse(
            risk_level=detail.risk_profile.risk_level,
            confidence=detail.risk_profile.confidence,
            signals=detail.risk_profile.signals,
            summary=detail.risk_profile.summary,
            main_reason=detail.risk_profile.main_reason,
        ),
        ai=AIInfoResponse(
            ai_status=detail.ai.ai_status,
            ai_score=detail.ai.ai_score,
            decision=detail.ai.decision.value if detail.ai.decision else None,
            explanation=detail.ai.explanation,
            ai_result=detail.ai.ai_result,
        ),
        history=HistoryResponse(
            created_at=detail.history.created_at,
            decision_at=detail.history.decision_at,
            telegram_action=detail.history.telegram_action,
        ),
    )


@router.get("/statistics", response_model=DashboardStatisticsResponse)
async def get_statistics(
    service: AdminDashboardService = Depends(get_admin_service),
) -> DashboardStatisticsResponse:
    stats = await service.get_statistics()
    return DashboardStatisticsResponse(
        total=stats.total,
        approved=stats.approved,
        rejected=stats.rejected,
        manual_review=stats.manual_review,
        pending=stats.pending,
        avg_rule_score=stats.avg_rule_score,
        avg_ai_score=stats.avg_ai_score,
    )


@router.post("/join-requests/{join_request_id}/approve", response_model=ActionResponse)
async def approve_join_request(
    join_request_id: uuid.UUID,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> ActionResponse:
    result = await action_service.approve(join_request_id)
    if not result.success and result.error == "not_found":
        raise HTTPException(status_code=404, detail=result.message)
    return ActionResponse(success=result.success, message=result.message, error=result.error)


@router.post("/join-requests/{join_request_id}/reject", response_model=ActionResponse)
async def reject_join_request(
    join_request_id: uuid.UUID,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> ActionResponse:
    result = await action_service.reject(join_request_id)
    if not result.success and result.error == "not_found":
        raise HTTPException(status_code=404, detail=result.message)
    return ActionResponse(success=result.success, message=result.message, error=result.error)


@router.post("/join-requests/{join_request_id}/whitelist", response_model=ActionResponse)
async def whitelist_join_request(
    join_request_id: uuid.UUID,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> ActionResponse:
    result = await action_service.whitelist(join_request_id)
    if not result.success and result.error == "not_found":
        raise HTTPException(status_code=404, detail=result.message)
    return ActionResponse(success=result.success, message=result.message, error=result.error)


@router.post("/join-requests/{join_request_id}/blacklist", response_model=ActionResponse)
async def blacklist_join_request(
    join_request_id: uuid.UUID,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> ActionResponse:
    result = await action_service.blacklist(join_request_id)
    if not result.success and result.error == "not_found":
        raise HTTPException(status_code=404, detail=result.message)
    return ActionResponse(success=result.success, message=result.message, error=result.error)
