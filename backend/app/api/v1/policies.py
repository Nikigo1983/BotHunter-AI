import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import require_api_dashboard_auth
from app.admin.auth.permissions import PERMISSION_CHANGE_SYSTEM_SETTINGS, has_permission
from app.database.session import get_db_session
from app.policy.types import PolicyThresholdConfig
from app.schemas.policy import (
    PolicyComparisonResponse,
    PolicyHistoryResponse,
    PolicyRollbackRequest,
    PolicySimulationRequest,
    PolicySimulationResponse,
    PolicyThresholdResponse,
    PolicyThresholdUpdateRequest,
    RulePolicyListResponse,
    RulePolicyResponse,
    RulePolicyUpdateRequest,
    SimulationDecisionDeltaResponse,
    PolicyVersionResponse,
)
from app.services.dashboard_auth import DashboardAuthContext
from app.services.policy import PolicyService
from app.services.policy_simulation import PolicySimulationService, SimulationRequest

router = APIRouter(
    prefix="/admin/policies",
    tags=["admin-policies"],
    dependencies=[Depends(require_api_dashboard_auth)],
)


async def get_policy_service(
    session: AsyncSession = Depends(get_db_session),
) -> PolicyService:
    return PolicyService(session)


async def get_simulation_service(
    session: AsyncSession = Depends(get_db_session),
) -> PolicySimulationService:
    return PolicySimulationService(session)


def _require_edit(auth: DashboardAuthContext) -> None:
    if not has_permission(auth.user.role, PERMISSION_CHANGE_SYSTEM_SETTINGS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _map_rule(item) -> RulePolicyResponse:
    return RulePolicyResponse(
        rule_key=item.rule_key,
        name=item.name,
        description=item.description,
        score=item.score,
        enabled=item.enabled,
        triggered_count=item.triggered_count,
        accuracy=item.accuracy,
        false_positives=item.false_positives,
        false_negatives=item.false_negatives,
        precision=item.precision,
        recall=item.recall,
        false_positive_rate=item.false_positive_rate,
        false_negative_rate=item.false_negative_rate,
        last_changed_at=item.last_changed_at,
        last_changed_by=item.last_changed_by,
        admin_comment=item.admin_comment,
    )


@router.get("", response_model=RulePolicyListResponse)
async def list_policies(
    service: PolicyService = Depends(get_policy_service),
) -> RulePolicyListResponse:
    rules = await service.list_rules()
    policy = await service.get_effective_policy()
    return RulePolicyListResponse(
        items=[_map_rule(item) for item in rules],
        version_number=policy.version_number,
        version_id=policy.version_id,
    )


@router.get("/history", response_model=PolicyHistoryResponse)
async def policy_history(
    service: PolicyService = Depends(get_policy_service),
) -> PolicyHistoryResponse:
    items = await service.list_history()
    return PolicyHistoryResponse(
        items=[
            PolicyVersionResponse(
                id=item.id,
                version_number=item.version_number,
                author=item.author,
                comment=item.comment,
                created_at=item.created_at,
                is_current=item.is_current,
                changed_rules=item.changed_rules,
            )
            for item in items
        ]
    )


@router.get("/compare", response_model=PolicyComparisonResponse)
async def compare_policies(
    service: PolicyService = Depends(get_policy_service),
) -> PolicyComparisonResponse:
    try:
        comparison = await service.compare_versions()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PolicyComparisonResponse(
        current_version=comparison.current_version,
        previous_version=comparison.previous_version,
        rule_changes=comparison.rule_changes,
        threshold_changes=comparison.threshold_changes,
    )


@router.get("/thresholds", response_model=PolicyThresholdResponse)
async def get_thresholds(
    service: PolicyService = Depends(get_policy_service),
) -> PolicyThresholdResponse:
    policy = await service.get_effective_policy()
    thresholds = policy.thresholds
    return PolicyThresholdResponse(
        approve_below=thresholds.approve_below,
        reject_from=thresholds.reject_from,
        trust_auto_approve=thresholds.trust_auto_approve,
        trust_auto_reject=thresholds.trust_auto_reject,
        ai_threshold=thresholds.ai_threshold,
    )


@router.patch("/thresholds", response_model=PolicyThresholdResponse)
async def update_thresholds(
    payload: PolicyThresholdUpdateRequest,
    auth: DashboardAuthContext = Depends(require_api_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
) -> PolicyThresholdResponse:
    _require_edit(auth)
    policy = await service.update_thresholds(
        approve_below=payload.approve_below,
        reject_from=payload.reject_from,
        trust_auto_approve=payload.trust_auto_approve,
        trust_auto_reject=payload.trust_auto_reject,
        ai_threshold=payload.ai_threshold,
        author=auth.user.email,
        comment=payload.comment,
    )
    thresholds = policy.thresholds
    return PolicyThresholdResponse(
        approve_below=thresholds.approve_below,
        reject_from=thresholds.reject_from,
        trust_auto_approve=thresholds.trust_auto_approve,
        trust_auto_reject=thresholds.trust_auto_reject,
        ai_threshold=thresholds.ai_threshold,
    )


@router.post("/simulate", response_model=PolicySimulationResponse)
async def simulate_policy(
    payload: PolicySimulationRequest,
    service: PolicySimulationService = Depends(get_simulation_service),
) -> PolicySimulationResponse:
    thresholds = None
    if payload.thresholds is not None:
        thresholds = PolicyThresholdConfig(
            approve_below=payload.thresholds.approve_below,
            reject_from=payload.thresholds.reject_from,
            trust_auto_approve=payload.thresholds.trust_auto_approve,
            trust_auto_reject=payload.thresholds.trust_auto_reject,
            ai_threshold=payload.thresholds.ai_threshold,
        )
    result = await service.simulate(
        SimulationRequest(
            rule_key=payload.rule_key,
            score=payload.score,
            enabled=payload.enabled,
            thresholds=thresholds,
            sample_size=payload.sample_size,
        )
    )
    return PolicySimulationResponse(
        sample_size=result.sample_size,
        baseline=SimulationDecisionDeltaResponse(
            approved=result.baseline.approved,
            rejected=result.baseline.rejected,
            manual_review=result.baseline.manual_review,
        ),
        simulated=SimulationDecisionDeltaResponse(
            approved=result.simulated.approved,
            rejected=result.simulated.rejected,
            manual_review=result.simulated.manual_review,
        ),
        delta=SimulationDecisionDeltaResponse(
            approved=result.delta.approved,
            rejected=result.delta.rejected,
            manual_review=result.delta.manual_review,
        ),
    )


@router.post("/rollback", response_model=RulePolicyListResponse)
async def rollback_policy(
    payload: PolicyRollbackRequest,
    auth: DashboardAuthContext = Depends(require_api_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
) -> RulePolicyListResponse:
    _require_edit(auth)
    try:
        await service.rollback(payload.version_id, author=auth.user.email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await list_policies(service)


@router.get("/{rule_key}", response_model=RulePolicyResponse)
async def get_policy_rule(
    rule_key: str,
    service: PolicyService = Depends(get_policy_service),
) -> RulePolicyResponse:
    rule = await service.get_rule(rule_key)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _map_rule(rule)


@router.patch("/{rule_key}", response_model=RulePolicyResponse)
async def update_policy_rule(
    rule_key: str,
    payload: RulePolicyUpdateRequest,
    auth: DashboardAuthContext = Depends(require_api_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
) -> RulePolicyResponse:
    _require_edit(auth)
    try:
        await service.update_rule(
            rule_key,
            score=payload.score,
            enabled=payload.enabled,
            description=payload.description,
            admin_comment=payload.admin_comment,
            author=auth.user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rule = await service.get_rule(rule_key)
    assert rule is not None
    return _map_rule(rule)
