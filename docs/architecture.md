# BotHunter AI — Architecture

## Overview

BotHunter AI follows clean architecture with clear separation of concerns.

**Текущая версия:** v0.4 — регистрация Telegram-каналов.

## Layers

```
Presentation   →  api/, bot/
Application    →  services/, schemas/
Domain         →  models/
Infrastructure →  database/, repositories/, config/, ai/, utils/
```

## Backend structure

| Folder      | Responsibility                          |
|-------------|-----------------------------------------|
| `api/`      | FastAPI routes and HTTP dependencies    |
| `bot/`      | Aiogram handlers and bot lifecycle      |
| `ai/`       | AI/ML integrations                      |
| `services/` | Business logic                          |
| `models/`   | SQLAlchemy ORM entities                 |
| `repositories/` | Data access layer (Generic Repository) |
| `schemas/`  | Pydantic request/response models        |
| `database/` | DB engine, sessions, base model         |
| `config/`   | Environment-based settings              |
| `utils/`    | Cross-cutting utilities (logging, etc.) |

## Domain model (v0.2)

Слой `models/` содержит ORM-сущности платформы:

| Модель | Назначение |
|--------|------------|
| `User` | Пользователь платформы |
| `TelegramBot` | Бот пользователя |
| `TelegramChannel` | Подключённый канал |
| `TelegramUser` | Telegram-пользователь, проходивший проверку |
| `JoinRequest` | Заявка на вступление |
| `AIAnalysis` | Результат AI-анализа |
| `Reputation` | Репутация Telegram-пользователя |
| `Blacklist` | Чёрный список |
| `Whitelist` | Белый список |
| `AuditLog` | Аудит действий |

Подробности, связи, индексы и ER-диаграмма: [docs/database.md](database.md).

## Repository layer (v0.3)

Слой `repositories/` реализует Generic Repository Pattern для всех доменных моделей.

- `BaseRepository` — CRUD: create, get_by_id, get_all, update, delete, exists, count.
- 10 entity-репозиториев — по одному на каждую модель.
- DI через factory-функции в `repositories/deps.py`.

Подробности: [docs/repositories.md](repositories.md).

## Channel registration (v0.4)

- Команда `/connect` в Telegram-боте.
- `ChannelRegistrationService` проверяет канал и права бота через Telegram API.
- Успешное подключение сохраняется в `telegram_channels`.
- Ошибки сохраняются в `channel_connection_errors`.

## Running locally

1. Copy `.env.example` to `.env` and fill in values.
2. Install dependencies: `pip install -r backend/requirements.txt`
3. Start API: `cd backend && python run.py`
4. Start bot: `cd backend && python -c "from run import run_bot; run_bot()"`

## Docker

```bash
docker compose -f docker/docker-compose.yml up --build
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## Migrations

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

В Docker:

```bash
docker exec bothunter-api alembic upgrade head
```

Текущая миграция: `657650f1297c` — `create_domain_models_v0_2`

## Changelog

См. [docs/changelog.md](changelog.md).
