import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.investigation.rule_inspector import RuleInspector
from app.investigation.timeline_builder import TimelineBuilder
from app.main import app
from app.models.ai_analysis import AIAnalysis
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.join_request import JoinRequest
from app.models.telegram_bot import TelegramBot
from app.models.telegram_channel import TelegramChannel
from app.models.telegram_user import TelegramUser
from app.repositories.deps import (
    get_ai_analysis_repository,
    get_audit_log_repository,
    get_investigation_repository,
    get_join_request_repository,
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_telegram_user_repository,
    get_user_repository,
)
from app.repositories.investigation import InvestigationFilters
from app.services.investigation import InvestigationService
from tests.conftest import make_user


async def seed_investigation_case(session: AsyncSession, *, suffix: str) -> JoinRequest:
    user_repo = get_user_repository(session)
    bot_repo = get_telegram_bot_repository(session)
    channel_repo = get_telegram_channel_repository(session)
    telegram_user_repo = get_telegram_user_repository(session)
    join_request_repo = get_join_request_repository(session)
    analysis_repo = get_ai_analysis_repository(session)

    owner = await user_repo.create(make_user(f"owner-{suffix}"))
    bot = await bot_repo.create(
        TelegramBot(owner_id=owner.id, bot_token="token", bot_username=f"bot_{suffix}")
    )
    channel = await channel_repo.create(
        TelegramChannel(
            owner_id=owner.id,
            bot_id=bot.id,
            telegram_chat_id=-1006000000 - abs(hash(suffix)) % 100000,
            title=f"Channel {suffix}",
            is_active=True,
        )
    )
    telegram_user = await telegram_user_repo.create(
        TelegramUser(
            telegram_id=940000 + abs(hash(suffix)) % 10000,
            username=f"inv_{suffix}",
            first_name="Investigate",
            last_name="Case",
            language_code="ru",
            is_premium=False,
            has_photo=False,
        )
    )
    join_request = await join_request_repo.create(
        JoinRequest(
            channel_id=channel.id,
            telegram_user_id=telegram_user.id,
            status=JoinRequestStatus.MANUAL_REVIEW,
        )
    )
    explanation = json.dumps(
        {
            "triggered_rules": [{"rule": "NoPhotoRule", "score": 20}],
            "risk_profile": {
                "risk_level": "MEDIUM",
                "confidence": 0.71,
                "signals": ["no_photo"],
                "summary": "Test summary",
                "trust_score": 55.0,
            },
            "ai_result": {
                "ai_score": 52,
                "decision": "ManualReview",
                "confidence": 0.82,
                "reason": "Test reason",
                "provider": "mock",
                "model": "mock-model",
            },
            "ai_status": "SUCCESS",
        },
        ensure_ascii=False,
    )
    await analysis_repo.create(
        AIAnalysis(
            join_request_id=join_request.id,
            rule_score=20.0,
            ai_score=52.0,
            final_score=36.0,
            decision=AnalysisDecision.MANUAL_REVIEW,
            explanation=explanation,
        )
    )
    return join_request


@pytest.mark.asyncio
async def test_rule_inspector_conditions(session: AsyncSession) -> None:
    join_request = await seed_investigation_case(session, suffix="rules")
    row = await get_investigation_repository(session).get_investigation(join_request.id)
    assert row is not None
    from app.features import FeatureExtractor

    features = FeatureExtractor().extract(row.telegram_user)
    items = RuleInspector().inspect(features)
    no_photo = next(item for item in items if item.rule == "NoPhotoRule")
    assert no_photo.matched is True
    assert no_photo.condition == "has_photo == false"
    assert no_photo.contribution == 20


@pytest.mark.asyncio
async def test_investigation_service_detail_timeline_and_export(session: AsyncSession) -> None:
    join_request = await seed_investigation_case(session, suffix="detail")
    service = InvestigationService(session)
    detail = await service.get_investigation_detail(join_request.id)
    assert detail is not None
    assert len(detail.timeline) >= 5
    assert detail.prompt is not None
    assert detail.ai_response.parsed_response is not None
    assert any(item.rule == "NoPhotoRule" for item in detail.rule_inspection)

    exported = await service.export_case(join_request.id, export_format="json")
    assert exported is not None
    content, media_type, filename = exported
    assert media_type == "application/json"
    assert b"timeline" in content
    assert filename.endswith(".json")

    pdf = await service.export_case(join_request.id, export_format="pdf", write_audit=False)
    assert pdf is not None
    assert pdf[0].startswith(b"%PDF")


@pytest.mark.asyncio
async def test_investigation_replay_writes_audit(session: AsyncSession) -> None:
    join_request = await seed_investigation_case(session, suffix="replay")
    service = InvestigationService(session)
    replay = await service.replay_analysis(join_request.id)
    assert replay is not None
    assert replay.rule_score >= 0
    assert replay.final_decision

    audit_repo = get_audit_log_repository(session)
    logs = await audit_repo.list_by_entity(entity="join_request", entity_id=join_request.id)
    assert any(log.action == "replay" for log in logs)


@pytest.mark.asyncio
async def test_investigation_repository_filters(session: AsyncSession) -> None:
    join_request = await seed_investigation_case(session, suffix="filter")
    repo = get_investigation_repository(session)
    result = await repo.list_investigations(
        filters=InvestigationFilters(search="Investigate"),
        offset=0,
        limit=10,
    )
    assert result.total >= 1
    assert any(row.join_request.id == join_request.id for row in result.rows)


@pytest.mark.asyncio
async def test_investigations_api_endpoints(session: AsyncSession) -> None:
    join_request = await seed_investigation_case(session, suffix="api")
    from app.database.session import get_db_session

    async def override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listing = await client.get("/api/v1/admin/investigations")
        assert listing.status_code == 200
        assert listing.json()["total"] >= 1

        detail = await client.get(f"/api/v1/admin/investigations/{join_request.id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["id"] == str(join_request.id)
        assert len(body["timeline"]) >= 1

        timeline = await client.get(f"/api/v1/admin/investigations/{join_request.id}/timeline")
        assert timeline.status_code == 200

        export_json = await client.get(
            f"/api/v1/admin/investigations/{join_request.id}/export?format=json"
        )
        assert export_json.status_code == 200
        assert export_json.headers["content-type"].startswith("application/json")

        replay = await client.post(f"/api/v1/admin/investigations/{join_request.id}/replay")
        assert replay.status_code == 200
        assert replay.json()["final_decision"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_investigations_web_pages(session: AsyncSession) -> None:
    join_request = await seed_investigation_case(session, suffix="web")
    from app.database.session import get_db_session

    async def override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        index = await client.get("/admin/investigations")
        assert index.status_code == 200
        assert "Investigation Center" in index.text

        detail = await client.get(f"/admin/join-request/{join_request.id}")
        assert detail.status_code == 200
        assert "Decision Timeline" in detail.text
        assert "Export JSON" in detail.text

        replay = await client.post(f"/admin/join-request/{join_request.id}/replay")
        assert replay.status_code == 303
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_timeline_builder_stages() -> None:
    from datetime import UTC, datetime

    created = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
    timeline = TimelineBuilder.build(
        created_at=created,
        analysis_created_at=created,
        explanation={
            "triggered_rules": [{"rule": "NoPhotoRule", "score": 20}],
            "risk_profile": {"risk_level": "MEDIUM", "summary": "test"},
            "ai_result": {"decision": "ManualReview", "provider": "mock"},
            "ai_status": "SUCCESS",
        },
        analysis_decision=AnalysisDecision.MANUAL_REVIEW,
        rule_score=20.0,
        join_status=JoinRequestStatus.MANUAL_REVIEW,
        telegram_action="left_pending",
        manual_reviews=[],
        audit_logs=[],
        rule_engine_decision=AnalysisDecision.MANUAL_REVIEW,
    )
    stages = [item.stage for item in timeline]
    assert "join_request_received" in stages
    assert "decision_engine" in stages
