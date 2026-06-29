import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.deps import get_telegram_user_repository, get_user_repository
from tests.conftest import make_user


@pytest.mark.asyncio
async def test_user_email_unique_constraint(session: AsyncSession) -> None:
    repo = get_user_repository(session)
    user = make_user("unique-email")
    duplicate = make_user("duplicate")
    duplicate.email = user.email

    await repo.create(user)

    with pytest.raises(IntegrityError):
        await repo.create(duplicate)


@pytest.mark.asyncio
async def test_telegram_user_telegram_id_unique_constraint(session: AsyncSession) -> None:
    from app.models.telegram_user import TelegramUser

    repo = get_telegram_user_repository(session)
    telegram_id = 4242424242

    await repo.create(
        TelegramUser(
            telegram_id=telegram_id,
            username="user_one",
            first_name="One",
            is_premium=False,
            has_photo=False,
        )
    )

    with pytest.raises(IntegrityError):
        await repo.create(
            TelegramUser(
                telegram_id=telegram_id,
                username="user_two",
                first_name="Two",
                is_premium=False,
                has_photo=False,
            )
        )
