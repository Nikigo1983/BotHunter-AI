# BotHunter AI — Architecture

## Overview

BotHunter AI follows clean architecture with clear separation of concerns.

**Текущая версия:** v1.7 — AI Analytics & Feedback Center.

## Layers

```
Presentation   →  api/, bot/
Application    →  services/, schemas/, rules/, features/, risk/, ai/
Domain         →  models/
Infrastructure →  database/, repositories/, config/, ai/, utils/
```

## Backend structure

| Folder      | Responsibility                          |
|-------------|-----------------------------------------|
| `api/`      | FastAPI routes and HTTP dependencies    |
| `bot/`      | Aiogram handlers and bot lifecycle      |
| `ai/`       | AI Layer (`AIService`, providers)       |
| `services/` | Business logic                          |
| `rules/`    | Rule Engine (profile scoring)           |
| `features/` | Feature extraction (`FeatureSet`)       |
| `risk/`     | Risk Profile (`RiskProfileBuilder`)     |
| `reputation/` | Reputation Engine (`ReputationService`) |
| `models/`   | SQLAlchemy ORM entities                 |
| `repositories/` | Data access layer (Generic Repository) |
| `explainability/` | Hybrid Explainability builder (v1.6) |
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
| `Reputation` | Репутация Telegram-пользователя (`trust_score`) |
| `ReputationHistory` | История изменений trust score (v1.3) |
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

## Channel registration (v1.0-beta)

- Команда `/connect` — инструкция (FSM только для UX).
- Chat ID формата `-100...` регистрирует канал **без зависимости от FSM**.
- `ChannelRegistrationService` проверяет канал и права бота через Telegram API.
- Успешное подключение сохраняется в `telegram_channels`.
- Ошибки сохраняются в `channel_connection_errors`.

Подробности: [docs/channel_registration.md](channel_registration.md).

## Admin Dashboard (v1.3)

- Trust Score на list/detail (цветовые бейджи: 80–100 зелёный, 40–79 жёлтый, 0–39 красный).
- Карточка **Average Trust Score** на главной.
- Секция **Reputation History** на странице заявки.
- REST API: `GET /api/v1/admin/reputation/{telegram_user_id}`.

Подробности: [docs/reputation.md](reputation.md), [docs/dashboard.md](dashboard.md).

## AI Gateway (v1.4)

- `OpenRouterProvider` — универсальный HTTP-провайдер через OpenRouter API (httpx, без OpenAI SDK).
- `AIRouter` — выбор provider по `AI_PROVIDER` (mock / openrouter / openai).
- Таблица `ai_usage` — статистика токенов, стоимости, latency.
- Dashboard: `/admin/ai`, `/admin/settings/ai`.
- Fallback на `MockAIProvider` при недоступности OpenRouter.

Подробности: [docs/openrouter.md](openrouter.md).

## AI Analytics & Feedback Center (v1.7)

- `AnalyticsRepository` — агрегирующие SQL-запросы (accuracy, rules, providers, timeline).
- `AnalyticsService` — маппинг DTO, Decision Inspector.
- Dashboard: `/admin/analytics`, расширенный `/admin/ai`.
- REST API: read-only `/api/v1/admin/analytics/*`.
- Decision Inspector на detail-странице заявки (AI vs Human).

Подробности: [docs/analytics.md](analytics.md).

## Reputation Engine (v1.3)

- `ReputationEngine` + `ReputationService` — расчёт `trust_score` (0–100, default 50).
- Таблица `reputation_history` — audit trail изменений.
- Join pipeline: trust ≥ 90 → auto APPROVED; trust ≤ 10 → auto REJECTED (без Rule Engine и AI).
- Admin actions обновляют репутацию (+5 approve, −10 reject, whitelist 100, blacklist 0).
- `RiskProfile.trust_score` передаётся в AI context (алгоритм builder не меняется).

Подробности: [docs/reputation.md](reputation.md).

## Admin Dashboard (v1.2)

- Интерактивные действия: Approve, Reject, Whitelist, Blacklist.
- `AdminJoinRequestActionService` → Telegram API → PostgreSQL → Audit/Feedback.
- Whitelist/blacklist интегрированы в join pipeline.

Подробности: [docs/dashboard.md](dashboard.md).

## Admin Dashboard (v1.1)

- Web UI: `/admin` (Jinja2 + HTMX + Bootstrap 5).
- REST API: `/api/v1/admin/*`.
- `AdminDashboardService` + DTO, read-only доступ к PostgreSQL через `AdminDashboardRepository`.

Подробности: [docs/dashboard.md](dashboard.md).

## Telegram Bot FSM

- FSM: `RedisStorage` (`app/bot/storage.py`), URL из `Settings.redis_url`.
- Состояния `/connect`, `/debug_chatid` и будущих сценариев переживают перезапуск бота.
- Redis уже используется в Docker Compose (`bothunter-redis`).

## Rule Engine (v0.5)

- Слой `rules/` — детерминированная оценка профиля `TelegramUser`.
- `BaseRule` + 9 правил + `RuleEngine`.
- Вход: `FeatureSet` (не `TelegramUser`).
- Возвращает `rule_score` и список `triggered_rules` (JSON).

Подробности: [docs/rule_engine.md](rule_engine.md).

## Feature Extraction (v0.7)

- `FeatureExtractor.extract(user)` → `FeatureSet`.
- Признаки Profile / Username / Name / System.
- Rule Engine работает только с `FeatureSet`.

Подробности: [docs/features.md](features.md).

## Risk Profile (v0.8)

- `RiskProfileBuilder.build(FeatureSet, RuleEngineResult, trust_score=...)` → `RiskProfile`.
- Поля: `risk_level`, `confidence`, `main_reason`, `signals`, `summary`, `trust_score` (v1.3).

Подробности: [docs/risk_profile.md](risk_profile.md).

## AI Layer (v0.9 / v1.4)

- `AIService` — AI только для `MANUAL_REVIEW`.
- **v1.4:** `OpenRouterProvider` + `AIRouter` — универсальный gateway для LLM.
- `MockAIProvider` — fallback и тесты.
- `OpenAIProvider` — legacy (OpenAI SDK).
- Retry (2), timeout (30s), fallback, `ai_usage` tracking.

Подробности: [docs/ai.md](ai.md), [docs/openrouter.md](openrouter.md).

## Join Request Processing (v1.0-beta)

- Handler `ChatJoinRequest` → `JoinRequestProcessingService`.
- FeatureExtractor → RuleEngine → RiskProfileBuilder → DecisionEngine.
- AI (`AIService`) только для `MANUAL_REVIEW`.
- Финальное решение, `AIAnalysis`, approve/decline/pending.
- Единые пороги через `get_decision_thresholds()` (YAML + env override).

Подробности: [docs/join_request_processing.md](join_request_processing.md).

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
