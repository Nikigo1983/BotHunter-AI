"""One-off script: process MANUAL_REVIEW join request with real OpenRouter."""
import asyncio
import json
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from aiogram.enums import ChatType
from aiogram.types import Chat, ChatJoinRequest, User as TelegramProfile
from sqlalchemy import select

from app.ai.enums import AIServiceStatus
from app.ai.router import AIRouter
from app.ai.service import AIService
from app.config import get_settings
from app.database.session import async_session_factory
from app.models.ai_usage import AIUsage
from app.repositories.deps import get_ai_usage_repository, get_telegram_channel_repository
from app.services.join_request_processing import JoinRequestProcessingService

CHAT_ID = -1004286145697
USER_ID = 998877666


async def main() -> int:
    settings = get_settings()
    primary = AIRouter.create_primary_provider()

    print("=== CONFIG ===")
    print(f"AI_PROVIDER={settings.ai_provider}")
    print(f"OPENROUTER_MODEL={settings.openrouter_model}")
    print(f"OPENROUTER_KEY configured={bool(settings.openrouter_api_key)}")
    print(f"Primary provider class: {primary.name}")

    async with async_session_factory() as session:
        channel = await get_telegram_channel_repository(session).get_by_telegram_chat_id(
            CHAT_ID
        )
        if channel is None:
            print(f"ERROR: channel {CHAT_ID} not registered")
            return 1

        mock_bot = AsyncMock()
        mock_bot.get_user_profile_photos.return_value = MagicMock(total_count=0)

        service = JoinRequestProcessingService(
            session,
            mock_bot,
            ai_service=AIService(),
        )

        event = ChatJoinRequest(
            chat=Chat(id=CHAT_ID, type=ChatType.CHANNEL, title=channel.title),
            from_user=TelegramProfile(
                id=USER_ID,
                is_bot=False,
                first_name="Test",
                last_name="Manual",
                username="user1234567",
                language_code=None,
                is_premium=False,
            ),
            user_chat_id=USER_ID,
            date=int(datetime.now(timezone.utc).timestamp()),
            bio=None,
        )

        result = await service.process(event)
        await session.commit()

        if result is None:
            print("ERROR: process returned None")
            return 1

        explanation = json.loads(result.analysis.explanation or "{}")
        ai_status = explanation.get("ai_status")
        ai_result = explanation.get("ai_result") or {}

        print("\n=== JOIN REQUEST ===")
        print(f"rule_score={result.rule_result.rule_score}")
        print(f"decision={result.decision.value}")
        print(f"status={result.join_request.status.value}")
        print(f"risk_level={result.risk_profile.risk_level.value}")

        print("\n=== AI SERVICE ===")
        print(f"ai_status={ai_status}")
        print(f"provider={ai_result.get('provider')}")
        print(f"model={ai_result.get('model')}")
        print(f"ai_score={ai_result.get('ai_score')}")
        print(f"prompt_tokens={ai_result.get('prompt_tokens')}")
        print(f"completion_tokens={ai_result.get('completion_tokens')}")
        print(f"total_tokens={ai_result.get('total_tokens')}")
        print(f"response_time_ms={ai_result.get('response_time_ms')}")

        latest = (
            await session.execute(
                select(AIUsage).order_by(AIUsage.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()

        print("\n=== AI_USAGE (latest row) ===")
        if latest is None:
            print("NO RECORD")
        else:
            print(f"provider={latest.provider}")
            print(f"model={latest.model}")
            print(f"prompt_tokens={latest.prompt_tokens}")
            print(f"completion_tokens={latest.completion_tokens}")
            print(f"total_tokens={latest.total_tokens}")
            print(f"estimated_cost=${latest.estimated_cost:.6f}")
            print(f"latency_ms={latest.latency_ms}")
            print(f"created_at={latest.created_at.isoformat()}")

        if ai_result.get("provider") != "openrouter":
            print("\nRESULT: NOT OpenRouter — see explanation above")
            return 2

        if ai_status not in {AIServiceStatus.SUCCESS.value, AIServiceStatus.FALLBACK.value}:
            print(f"\nRESULT: AI status={ai_status}")
            return 2

        print("\nRESULT: OpenRouter call confirmed")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
