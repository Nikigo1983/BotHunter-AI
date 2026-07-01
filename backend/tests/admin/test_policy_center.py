import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.policy.types import build_default_rule_configs
from app.repositories.deps import get_policy_repository
from app.services.policy import PolicyService
from app.services.policy_simulation import PolicySimulationService, SimulationRequest
from tests.admin.test_investigations import seed_investigation_case


@pytest.mark.asyncio
async def test_ensure_initial_policy(session: AsyncSession) -> None:
    service = PolicyService(session)
    await service.ensure_initial_policy()
    policy = await service.get_effective_policy()
    assert policy.version_number == 1
    assert len(policy.rules) == len(build_default_rule_configs())
    assert policy.thresholds.approve_below == 30
    assert policy.thresholds.reject_from == 70


@pytest.mark.asyncio
async def test_update_rule_creates_version(session: AsyncSession) -> None:
    service = PolicyService(session)
    await service.ensure_initial_policy()
    await service.update_rule(
        "NoPhotoRule",
        score=15,
        enabled=True,
        description="No profile photo",
        admin_comment="Lower weight",
        author="admin@test.local",
    )
    rule = await service.get_rule("NoPhotoRule")
    assert rule is not None
    assert rule.score == 15
    history = await service.list_history(limit=5)
    assert history[0].version_number == 2
    assert "NoPhotoRule" in history[0].changed_rules


@pytest.mark.asyncio
async def test_simulation_does_not_change_current_policy(session: AsyncSession) -> None:
    service = PolicyService(session)
    simulation = PolicySimulationService(session)
    await service.ensure_initial_policy()
    before = await service.get_effective_policy()
    before_score = before.rules["NoPhotoRule"].score
    result = await simulation.simulate(
        SimulationRequest(rule_key="NoPhotoRule", score=before_score - 5)
    )
    assert result.sample_size >= 0
    after = await service.get_effective_policy()
    assert after.version_number == before.version_number
    assert after.rules["NoPhotoRule"].score == before_score


@pytest.mark.asyncio
async def test_rollback_restores_snapshot(session: AsyncSession) -> None:
    service = PolicyService(session)
    await service.ensure_initial_policy()
    v1 = await service.get_effective_policy()
    await service.update_rule(
        "NoPhotoRule",
        score=5,
        enabled=True,
        description="No profile photo",
        admin_comment=None,
        author="admin@test.local",
    )
    history = await service.list_history(limit=5)
    v1_row = next(item for item in history if item.version_number == 1)
    rolled = await service.rollback(v1_row.id, author="admin@test.local")
    assert rolled.version_number == 3
    rule = await service.get_rule("NoPhotoRule")
    assert rule is not None
    assert rule.score == v1.rules["NoPhotoRule"].score


@pytest.mark.asyncio
async def test_compare_versions(session: AsyncSession) -> None:
    service = PolicyService(session)
    await service.ensure_initial_policy()
    await service.update_rule(
        "TooManyEmojiRule",
        score=12,
        enabled=False,
        description="Too many emoji in name",
        admin_comment="Disable noisy rule",
        author="admin@test.local",
    )
    comparison = await service.compare_versions()
    assert comparison.current_version == 2
    assert comparison.previous_version == 1
    assert any(item["rule_key"] == "TooManyEmojiRule" for item in comparison.rule_changes)


@pytest.mark.asyncio
async def test_policies_api_endpoints(session: AsyncSession, admin_client: AsyncClient) -> None:
    service = PolicyService(session)
    await service.ensure_initial_policy()

    listing = await admin_client.get("/api/v1/admin/policies")
    assert listing.status_code == 200
    body = listing.json()
    assert body["version_number"] == 1
    assert len(body["items"]) >= 9

    detail = await admin_client.get("/api/v1/admin/policies/NoPhotoRule")
    assert detail.status_code == 200
    assert detail.json()["rule_key"] == "NoPhotoRule"

    patch = await admin_client.patch(
        "/api/v1/admin/policies/NoPhotoRule",
        json={
            "score": 18,
            "enabled": True,
            "description": "No profile photo",
            "admin_comment": "API update",
        },
    )
    assert patch.status_code == 200
    assert patch.json()["score"] == 18

    simulate = await admin_client.post(
        "/api/v1/admin/policies/simulate",
        json={"rule_key": "NoPhotoRule", "score": 10, "sample_size": 10},
    )
    assert simulate.status_code == 200
    assert "delta" in simulate.json()

    history = await admin_client.get("/api/v1/admin/policies/history")
    assert history.status_code == 200
    assert len(history.json()["items"]) >= 2

    compare = await admin_client.get("/api/v1/admin/policies/compare")
    assert compare.status_code == 200

    thresholds = await admin_client.get("/api/v1/admin/policies/thresholds")
    assert thresholds.status_code == 200

    threshold_patch = await admin_client.patch(
        "/api/v1/admin/policies/thresholds",
        json={
            "approve_below": 25,
            "reject_from": 75,
            "trust_auto_approve": 90,
            "trust_auto_reject": 10,
            "ai_threshold": 0.8,
            "comment": "Tighten thresholds",
        },
    )
    assert threshold_patch.status_code == 200
    assert threshold_patch.json()["approve_below"] == 25

    versions = history.json()["items"]
    old_version = next(item for item in versions if item["version_number"] == 1)
    rollback = await admin_client.post(
        "/api/v1/admin/policies/rollback",
        json={"version_id": old_version["id"]},
    )
    assert rollback.status_code == 200


@pytest.mark.asyncio
async def test_policies_web_pages(session: AsyncSession, admin_client: AsyncClient, admin_csrf: str) -> None:
    await PolicyService(session).ensure_initial_policy()

    index = await admin_client.get("/admin/policies")
    assert index.status_code == 200
    assert "Policy Center" in index.text
    assert "NoPhotoRule" in index.text

    detail = await admin_client.get("/admin/policies/NoPhotoRule")
    assert detail.status_code == 200
    assert "Rule Simulator" in detail.text

    history = await admin_client.get("/admin/policies/history")
    assert history.status_code == 200

    compare = await admin_client.get("/admin/policies/compare")
    assert compare.status_code in {200, 404}

    thresholds = await admin_client.get("/admin/policies/thresholds")
    assert thresholds.status_code == 200

    save = await admin_client.post(
        "/admin/policies/NoPhotoRule",
        data={
            "csrf_token": admin_csrf,
            "score": "17",
            "enabled": "on",
            "description": "No profile photo",
            "admin_comment": "Web update",
        },
        follow_redirects=False,
    )
    assert save.status_code == 303


@pytest.mark.asyncio
async def test_replay_with_policy_version(session: AsyncSession, admin_client: AsyncClient, admin_csrf: str) -> None:
    service = PolicyService(session)
    await service.ensure_initial_policy()
    join_request = await seed_investigation_case(session, suffix="policy-replay")

    await service.update_rule(
        "NoPhotoRule",
        score=25,
        enabled=True,
        description="No profile photo",
        admin_comment=None,
        author="admin@test.local",
    )
    history = await service.list_history(limit=5)
    v1 = next(item for item in history if item.version_number == 1)

    current = await admin_client.post(
        f"/api/v1/admin/investigations/{join_request.id}/replay",
        json={},
    )
    assert current.status_code == 200

    historical = await admin_client.post(
        f"/api/v1/admin/investigations/{join_request.id}/replay",
        json={"policy_version_id": str(v1.id)},
    )
    assert historical.status_code == 200
    assert historical.json()["policy_version_number"] == 1

    web_replay = await admin_client.post(
        f"/admin/join-request/{join_request.id}/replay",
        data={"csrf_token": admin_csrf, "policy_version_id": str(v1.id)},
        follow_redirects=False,
    )
    assert web_replay.status_code == 303
