import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import require_api_dashboard_auth
from app.database.session import get_db_session
from app.models.enums import AnalysisDecision
from app.schemas.investigation import (
    InvestigationDetailResponse,
    InvestigationListResponse,
    InvestigationListItemResponse,
    ReplayResponse,
    TimelineEventResponse,
)
from app.services.investigation import InvestigationService

router = APIRouter(
    prefix="/admin/investigations",
    tags=["admin-investigations"],
    dependencies=[Depends(require_api_dashboard_auth)],
)


async def get_investigation_service(
    session: AsyncSession = Depends(get_db_session),
) -> InvestigationService:
    return InvestigationService(session)


def _serialize_detail(detail) -> InvestigationDetailResponse:
    return InvestigationDetailResponse(
        id=detail.case.id,
        channel_id=detail.channel_id,
        channel_title=detail.case.channel_title,
        status=detail.case.status.value,
        timeline=[
            TimelineEventResponse(
                stage=item.stage,
                title=item.title,
                timestamp=item.timestamp,
                duration_ms=item.duration_ms,
                result=item.result,
                details=item.details,
            )
            for item in detail.timeline
        ],
        prompt=(
            {
                "system": detail.prompt.system_prompt,
                "user": detail.prompt.user_prompt,
            }
            if detail.prompt
            else None
        ),
        ai_response={
            "parsed": detail.ai_response.parsed_response,
            "raw_json": detail.ai_response.raw_json,
            "ai_status": detail.ai_response.ai_status,
        },
        rule_inspection=[
            {
                "rule": item.rule,
                "condition": item.condition,
                "description": item.description,
                "matched": item.matched,
                "contribution": item.contribution,
            }
            for item in detail.rule_inspection
        ],
        decision_flow={
            "rule_engine_decision": detail.decision_flow.rule_engine_decision,
            "ai_decision": detail.decision_flow.ai_decision,
            "final_decision": detail.decision_flow.final_decision,
            "human_decision": detail.decision_flow.human_decision,
            "ai_matches_human": detail.decision_flow.ai_matches_human,
            "verdict": detail.decision_flow.verdict,
            "verdict_class": detail.decision_flow.verdict_class,
        },
        audit_logs=[
            {
                "id": str(item.id),
                "created_at": item.created_at.isoformat(),
                "actor": item.actor,
                "action": item.action,
                "details": item.details,
            }
            for item in detail.audit_logs
        ],
        case={
            "id": str(detail.case.id),
            "channel_title": detail.case.channel_title,
            "status": detail.case.status.value,
            "rule_score": detail.case.rule_score,
            "ai_score": detail.case.ai_score,
            "final_score": detail.case.final_score,
            "trust_score": detail.case.trust_score,
            "user": {
                "telegram_id": detail.case.user.telegram_id,
                "username": detail.case.user.username,
                "first_name": detail.case.user.first_name,
                "last_name": detail.case.user.last_name,
            },
        },
    )


@router.get("", response_model=InvestigationListResponse)
async def list_investigations(
    channel_id: uuid.UUID | None = None,
    status: str = Query(default="all"),
    ai_decision: AnalysisDecision | None = None,
    human_decision: AnalysisDecision | None = None,
    trust_min: float | None = Query(default=None, ge=0, le=100),
    trust_max: float | None = Query(default=None, ge=0, le=100),
    rule_min: float | None = Query(default=None, ge=0, le=100),
    rule_max: float | None = Query(default=None, ge=0, le=100),
    ai_min: float | None = Query(default=None, ge=0, le=100),
    ai_max: float | None = Query(default=None, ge=0, le=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationListResponse:
    filters = InvestigationService.build_filters(
        channel_id=channel_id,
        status=status,
        ai_decision=ai_decision,
        human_decision=human_decision,
        trust_min=trust_min,
        trust_max=trust_max,
        rule_min=rule_min,
        rule_max=rule_max,
        ai_min=ai_min,
        ai_max=ai_max,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    result = await service.list_investigations(filters=filters, page=page, page_size=page_size)
    return InvestigationListResponse(
        items=[
            InvestigationListItemResponse(
                id=item.id,
                created_at=item.created_at,
                channel_id=item.channel_id,
                channel_title=item.channel_title,
                telegram_id=item.telegram_id,
                username=item.username,
                first_name=item.first_name,
                last_name=item.last_name,
                status=item.status.value,
                rule_score=item.rule_score,
                ai_score=item.ai_score,
                final_score=item.final_score,
                ai_decision=item.ai_decision,
                human_decision=item.human_decision,
                trust_score=item.trust_score,
            )
            for item in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.get("/{investigation_id}", response_model=InvestigationDetailResponse)
async def get_investigation(
    investigation_id: uuid.UUID,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationDetailResponse:
    detail = await service.get_investigation_detail(investigation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return _serialize_detail(detail)


@router.get("/{investigation_id}/timeline", response_model=list[TimelineEventResponse])
async def get_investigation_timeline(
    investigation_id: uuid.UUID,
    service: InvestigationService = Depends(get_investigation_service),
) -> list[TimelineEventResponse]:
    timeline = await service.get_timeline(investigation_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return [
        TimelineEventResponse(
            stage=item.stage,
            title=item.title,
            timestamp=item.timestamp,
            duration_ms=item.duration_ms,
            result=item.result,
            details=item.details,
        )
        for item in timeline
    ]


@router.get("/{investigation_id}/export")
async def export_investigation(
    investigation_id: uuid.UUID,
    format: str = Query(default="json", pattern="^(json|pdf)$"),
    service: InvestigationService = Depends(get_investigation_service),
) -> Response:
    exported = await service.export_case(investigation_id, export_format=format)
    if exported is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    content, media_type, filename = exported
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{investigation_id}/replay", response_model=ReplayResponse)
async def replay_investigation(
    investigation_id: uuid.UUID,
    service: InvestigationService = Depends(get_investigation_service),
) -> ReplayResponse:
    replay = await service.replay_analysis(investigation_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return ReplayResponse(
        rule_score=replay.rule_score,
        rule_engine_decision=replay.rule_engine_decision,
        ai_status=replay.ai_status,
        ai_decision=replay.ai_decision,
        ai_score=replay.ai_score,
        final_decision=replay.final_decision,
        prompt={
            "system": replay.prompt.system_prompt,
            "user": replay.prompt.user_prompt,
        },
        ai_response=replay.ai_response,
        triggered_rules=replay.triggered_rules,
    )
