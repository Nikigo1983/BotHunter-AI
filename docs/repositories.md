# BotHunter AI — Repository Layer

## Обзор

Слой `repositories/` (v0.3) инкапсулирует доступ к данным через Generic Repository Pattern поверх SQLAlchemy Async Session.

```
Application (services)  →  repositories/  →  models/  →  PostgreSQL
```

---

## BaseRepository

Файл: `backend/app/repositories/base.py`

Generic-класс `BaseRepository[ModelT]` принимает `AsyncSession` и ORM-модель.

| Метод | Описание |
|-------|----------|
| `create(entity)` | Создание записи (`add` + `flush` + `refresh`) |
| `get_by_id(entity_id)` | Получение по UUID |
| `get_all(offset, limit)` | Список записей с пагинацией |
| `update(entity)` | Обновление (`flush` + `refresh`) |
| `delete(entity)` | Удаление сущности |
| `delete_by_id(entity_id)` | Удаление по UUID, возвращает `bool` |
| `exists(entity_id)` | Проверка существования |
| `count()` | Количество записей |

---

## Entity Repositories

| Repository | Модель | Файл |
|------------|--------|------|
| `UserRepository` | `User` | `user.py` |
| `TelegramBotRepository` | `TelegramBot` | `telegram_bot.py` |
| `TelegramChannelRepository` | `TelegramChannel` | `telegram_channel.py` |
| `TelegramUserRepository` | `TelegramUser` | `telegram_user.py` |
| `JoinRequestRepository` | `JoinRequest` | `join_request.py` |
| `AIAnalysisRepository` | `AIAnalysis` | `ai_analysis.py` |
| `BlacklistRepository` | `Blacklist` | `blacklist.py` |
| `WhitelistRepository` | `Whitelist` | `whitelist.py` |
| `ReputationRepository` | `Reputation` | `reputation.py` |
| `AuditLogRepository` | `AuditLog` | `audit_log.py` |

Все entity-репозитории наследуют `BaseRepository` без дублирования CRUD-логики.

---

## Dependency Injection

Файл: `backend/app/repositories/deps.py`

Factory-функции для внедрения репозиториев через `AsyncSession`:

```python
from app.database import get_db_session
from app.repositories.deps import get_user_repository

async def example(session=Depends(get_db_session)):
    repo = get_user_repository(session)
    user = await repo.get_by_id(user_id)
```

Доступные factory:

- `get_user_repository`
- `get_telegram_bot_repository`
- `get_telegram_channel_repository`
- `get_telegram_user_repository`
- `get_join_request_repository`
- `get_ai_analysis_repository`
- `get_blacklist_repository`
- `get_whitelist_repository`
- `get_reputation_repository`
- `get_audit_log_repository`

---

## Структура каталога

```
backend/app/repositories/
├── __init__.py
├── base.py
├── deps.py
├── user.py
├── telegram_bot.py
├── telegram_channel.py
├── telegram_user.py
├── join_request.py
├── ai_analysis.py
├── blacklist.py
├── whitelist.py
├── reputation.py
└── audit_log.py
```

---

## Тестирование

Тесты: `backend/tests/repositories/`

| Файл | Покрытие |
|------|----------|
| `test_crud.py` | CRUD для `UserRepository`, create/get для всех репозиториев |
| `test_unique_constraints.py` | Unique constraints (`users.email`, `telegram_users.telegram_id`) |
| `test_cascade_delete.py` | CASCADE DELETE (`User` → `TelegramBot`, `TelegramChannel`) |
| `test_transactions.py` | Rollback и commit транзакций |

Запуск:

```bash
cd backend
python -m pytest tests/ -v
```

В Docker:

```bash
docker exec bothunter-api python -m pytest tests/ -v
```

---

## Принципы

- Только доступ к данным — без бизнес-логики.
- Async-only через `AsyncSession`.
- Type hints и Generic Repository.
- DI через factory-функции в `deps.py`.
- Services (следующий этап) будут использовать repositories, не models напрямую.
