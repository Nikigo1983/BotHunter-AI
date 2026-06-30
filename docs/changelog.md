# BotHunter AI — Changelog

## [1.2.0] — 2026-06-30

### Added

- Admin Actions: Approve, Reject, Whitelist, Blacklist (Web + REST API).
- `AdminJoinRequestActionService` с Telegram API, audit log, feedback loop.
- Таблицы: `manual_reviews`, `ai_feedbacks`.
- Whitelist/blacklist short-circuit в `JoinRequestProcessingService`.
- Dashboard UI: flash messages, disabled buttons, Manual Review History, AI Feedback.
- Бейджи Whitelisted/Blacklisted на главной странице.
- Unit + integration tests для admin actions и list-match pipeline.

---

## [1.1.0] — 2026-06-30

### Added

- Admin Dashboard MVP: `/admin` (Jinja2 + HTMX + Bootstrap 5).
- REST API: `GET /api/v1/admin/join-requests`, `GET /api/v1/admin/join-requests/{id}`, `GET /api/v1/admin/statistics`.
- `AdminDashboardService`, DTO, `AdminDashboardRepository` (read-only queries).
- Фильтры, поиск, пагинация (25), карточки статистики.
- Detail page: user, Feature Set, Rule Engine, Risk Profile, AI, History.
- Unit + integration tests.
- Документация: `docs/dashboard.md`.

### Not included (by design)

- Approve/Reject/Whitelist/Blacklist actions (заглушки)
- OpenAI
- React/Vue frontend

---

## [1.0.0-beta.2] — 2026-06-30

### Changed

- FSM бота: `MemoryStorage` → `RedisStorage` (состояния переживают перезапуск).
- Factory: `app/bot/storage.py`, URL из `Settings.redis_url`.

---

## [1.0.0-beta.1] — 2026-06-30

### Fixed

- Регистрация канала через `/connect` больше не зависит от FSM.
- Chat ID формата `-100...` обрабатывается напрямую (устойчиво к рестарту и `/debug_chatid`).
- Документация: `docs/channel_registration.md`.

---

## [1.0.0-beta] — 2026-06-29

### Fixed (Integration Audit)

- **Production pipeline:** `JoinRequestProcessingService` интегрирует `RiskProfileBuilder` + `AIService`.
- **AI только для MANUAL_REVIEW:** APPROVED/REJECTED без вызова AI.
- **Final decision:** из `AIAnalysisResult` при SUCCESS/FALLBACK; `AI_UNAVAILABLE` → MANUAL_REVIEW.
- **AIAnalysis:** `ai_score`, `final_score` (среднее rule+ai), расширенный `explanation` JSON.
- **Единые пороги:** `get_decision_thresholds()` — YAML + env override; `RiskProfileBuilder` использует те же пороги.
- **Error handling:** try/except + rollback в join handler; Telegram API errors не роняют обработку.
- **Docker:** bot healthcheck через `kill -0 1` (живой процесс).
- **E2E tests:** полный pipeline LOW / MEDIUM / HIGH.
- **Docs:** architecture, join_request_processing, ai, README, pyproject version.

---

## [0.9.0] — 2026-06-29

### Added

- AI Layer: `app/ai/`.
- `AIProvider` — интерфейс провайдера AI.
- `MockAIProvider` — детерминированный провайдер для тестов и fallback.
- `OpenAIProvider` — OpenAI SDK + Structured Output (JSON).
- `PromptBuilder` — prompt без персональных данных (Risk Level, Confidence, Signals, Summary).
- `AIService` — AI только для `MANUAL_REVIEW`; retry (2), timeout, fallback, logging.
- `AIAnalysisResult`, `AIServiceResult`, `AIServiceStatus` (`AI_UNAVAILABLE`).
- Unit и integration tests для AI Layer.
- Документация: `docs/ai.md` + Mermaid-диаграмма.
- Зависимость: `openai==1.59.6`.
- Настройки: `OPENAI_MODEL`, `OPENAI_TIMEOUT`.

### Not included (by design)

- Интеграция AI в `JoinRequestProcessingService`
- Изменения Rule Engine, Feature Extraction, Decision Engine, Repository Layer

---

## [0.8.0] — 2026-06-29

### Added

- Risk Profile Engine: `app/risk/`.
- `RiskProfileBuilder` — преобразование `FeatureSet` + `RuleEngineResult` → `RiskProfile`.
- Dataclass `RiskProfile`: `risk_level`, `confidence`, `main_reason`, `signals`, `summary`.
- Unit tests для LOW / MEDIUM / HIGH и комбинаций сигналов.
- Документация: `docs/risk_profile.md` + Mermaid-диаграмма.

### Not included (by design)

- OpenAI
- Изменения `RuleEngine`, `DecisionEngine`, `JoinRequest`

---

## [0.7.0] — 2026-06-29

### Added

- Feature Extraction Engine: `app/features/`.
- `FeatureExtractor` + dataclass `FeatureSet`.
- Признаки Profile, Username, Name, System.
- Rule Engine переведён на работу только с `FeatureSet`.
- Unit tests для каждого признака.
- Документация: `docs/features.md`.

### Changed

- `JoinRequestProcessingService` вызывает `FeatureExtractor` перед `RuleEngine`.
- `BaseRule.calculate()` принимает `FeatureSet` вместо `TelegramUser`.

### Not included (by design)

- OpenAI
- Изменения `DecisionEngine`
- Изменения модели `JoinRequest`

---

## [0.6.0] — 2026-06-29

### Added

- Обработчик `ChatJoinRequest` (Aiogram 3).
- `JoinRequestProcessingService` — полный цикл обработки заявки.
- `DecisionEngine` — APPROVED / MANUAL_REVIEW / REJECTED по `rule_score`.
- Конфигурация порогов: `backend/config/decision_thresholds.yaml` + `.env`.
- Автоматический approve/decline через Telegram API.
- Сохранение `JoinRequest`, `AIAnalysis`, upsert `TelegramUser`.
- Логирование обработки заявок.
- Unit и integration tests.
- Документация: `docs/join_request_processing.md`.

### Decision thresholds

- `rule_score < 30` → APPROVED
- `30–69` → MANUAL_REVIEW
- `≥ 70` → REJECTED

### Not included (by design)

- OpenAI
- Dashboard

---

## [0.5.0] — 2026-06-29

### Added

- Rule Engine: `app/rules/`.
- `BaseRule` — интерфейс правил (`calculate`, `description`, `weight`).
- 9 правил оценки профиля `TelegramUser`.
- `RuleEngine` — агрегация score и JSON-результата.
- Unit tests для каждого правила и движка.
- Документация: `docs/rule_engine.md` + Mermaid-диаграмма.

### Rules

- `NoPhotoRule` (+20)
- `NoUsernameRule` (+10)
- `UsernameManyDigitsRule` (+15)
- `UsernameConsecutiveDigitsRule` (+20)
- `SuspiciousNameWordsRule` (+20)
- `LongNameRule` (+10)
- `TooManyEmojiRule` (+15)
- `EmptyNameRule` (+30)
- `UnknownLanguageRule` (+5)

### Not included (by design)

- OpenAI / AI
- Decision logic (approve/reject)
- Join Request processing
- Dashboard

---

## [0.4.0] — 2026-06-29

### Added

- Команда Telegram-бота `/connect` для регистрации каналов.
- FSM-сценарий ожидания ID канала.
- `ChannelRegistrationService` — проверка канала и прав через Telegram API.
- Модель и таблица `channel_connection_errors` для ошибок подключения.
- `ChannelConnectionErrorRepository`.
- Тесты регистрации каналов и handler `/connect`.

### Channel registration

- Проверка существования канала (`getChat`).
- Проверка статуса администратора бота (`getChatMember`).
- Проверка прав: **Invite Users** (`can_invite_users`), **Manage Join Requests** (`can_manage_chat`).
- Сохранение канала через `TelegramChannelRepository`.
- Логирование неудачных попыток в `channel_connection_errors`.

### Not included (by design)

- AI
- Rule Engine
- Dashboard
- Join Request processing

---

## [0.3.0] — 2026-06-29

### Added

- Слой Repository: `app/repositories/`.
- `BaseRepository[ModelT]` с Generic CRUD-методами.
- 10 entity-репозиториев для всех доменных моделей.
- Dependency Injection через factory-функции (`repositories/deps.py`).
- Unit/integration tests: CRUD, unique constraints, cascade delete, transactions.
- Документация: `docs/repositories.md`.
- Зависимости для тестирования: `pytest`, `pytest-asyncio`.

### Repositories

- `UserRepository`
- `TelegramBotRepository`
- `TelegramChannelRepository`
- `TelegramUserRepository`
- `JoinRequestRepository`
- `AIAnalysisRepository`
- `BlacklistRepository`
- `WhitelistRepository`
- `ReputationRepository`
- `AuditLogRepository`

### Not included (by design)

- API endpoints
- Business services
- AI logic
- Telegram handlers changes
- Dashboard

---

## [0.2.0] — 2026-06-29

### Added

- Доменная модель платформы (10 SQLAlchemy-моделей).
- PostgreSQL ENUM: `join_request_status`, `analysis_decision`.
- UUID-первичные ключи для всех сущностей.
- ForeignKey-связи между пользователями, ботами, каналами и заявками.
- Индексы и unique constraints для часто используемых полей.
- Alembic-миграция `657650f1297c_create_domain_models_v0_2`.
- Документация: `docs/database.md`, ER-диаграмма Mermaid.

### Domain entities

- `User`
- `TelegramBot`
- `TelegramChannel`
- `TelegramUser`
- `JoinRequest`
- `AIAnalysis`
- `Reputation`
- `Blacklist`
- `Whitelist`
- `AuditLog`

### Not included (by design)

- API endpoints
- Business services
- AI logic
- Telegram handlers changes
- Dashboard

---

## [0.1.0] — 2026-06-29

### Added

- Каркас проекта: FastAPI, Aiogram 3, PostgreSQL, Redis, Docker.
- Health endpoint и Swagger.
- Telegram-бот: `/start`, `/help`, логирование сообщений.
- Базовая документация архитектуры.
