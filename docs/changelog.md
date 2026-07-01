# BotHunter AI — Changelog

## [2.1.0] — 2026-06-30

### Added — Adaptive Intelligence & Policy Center

- **Policy Center** — `/admin/policies` lists all Rule Engine rules with score, enabled, analytics, last change.
- **Rule Editor** — `/admin/policies/{rule}` edit score, enabled, description, admin comment without Python changes.
- **Rule Simulator** — dry-run last 100 join requests before save (Approve/Reject/Manual deltas, no DB writes).
- **Policy Versioning** — every change creates Policy vN; history + rollback to any snapshot.
- **Decision Replay** — Investigation Center replay with Current Policy or Policy vN.
- **Global Threshold Editor** — `/admin/policies/thresholds` for approve/reject/trust/AI thresholds (not `.env`).
- **Policy Comparison** — current vs previous diff for scores, enabled, thresholds.
- **Rule Analytics** — accuracy, precision, recall, FPR/FNR per rule (from Analytics + feedback).
- `PolicyRepository`, `PolicyService`, `PolicySimulationService`, configurable `BaseRule`.
- REST API: `/api/v1/admin/policies`, simulate, rollback, history, compare, thresholds.
- Migration `h8i9j0k2l3m4`, docs: `docs/policy_center.md`.
- Tests: `tests/admin/test_policy_center.py`.

### Changed

- `JoinRequestProcessingService` loads effective policy from DB when engines not injected (tests unchanged).
- Dashboard nav: Policies after Channels.

### Not changed (by design)

- Telegram Bot, AI Gateway, OpenRouterProvider, Authentication, Investigation Center core

---

## [2.0.0] — 2026-06-30

### Added — Production Readiness

- **Dashboard auth** — login/logout, bcrypt passwords, HttpOnly session cookie, CSRF on POST forms.
- **Roles** — Owner, Administrator, Moderator, Viewer with permission checks.
- **Settings UI** — `/admin/settings` edits AI provider/model/timeout/retry/thresholds/budget in DB (no `.env` edit).
- **System monitor** — `/admin/system` with health checks, Production Ready score, usage, Docker/host metrics.
- **Error Center**, **Queue monitor**, **Usage limits**, **Backup/Restore** (JSON/SQL/CSV), **Secrets** (masked), **Logs**, **Notification Center**.
- REST admin API protected by session auth.
- Migration `g7h8i9j0k1l2`, docs: `docs/production_readiness.md`.
- Tests: 190 passed (including `tests/admin/test_production_v2.py`).

### Default login (first startup)

- Email: `admin@bothunter.local`
- Password: `admin` (change via env: `DASHBOARD_ADMIN_*`)

---

## [1.9.0] — 2026-06-30

### Added

- **Investigation Center & Decision Audit** — `/admin/investigations`, full case timeline on join request detail.
- Decision Comparator (Rule → AI → Final → Human), Rule Inspector with conditions, Prompt/Response viewers.
- Export JSON + Export PDF, Replay Analysis (no DB/Telegram changes).
- `InvestigationRepository`, `InvestigationService`, `RuleInspector`, `TimelineBuilder`.
- REST API: `/api/v1/admin/investigations`, timeline, export, replay.
- Audit extension: `audit_logs.details` + logging for replay/export.
- Documentation: `docs/investigation_center.md`; updated dashboard, API, architecture.
- Tests: repository, service, API, web, replay, export, timeline, audit.

### Not changed (by design)

- Rule Engine, AI Gateway, OpenRouter, Reputation Engine
- Join Pipeline business logic

---

## [1.8.0] — 2026-06-30

### Added

- **Channel Management & Configuration Center** — `/admin/channels`, `/admin/channels/{id}`.
- Таблица `channel_settings` — per-channel AI flag, rule/reputation thresholds, join request timeout.
- `ChannelRepository`, `ChannelSettingsRepository`, `ChannelStatisticsRepository`.
- `AdminChannelService` — list, detail, statistics, settings update, enable/disable.
- REST API: `GET/PATCH /api/v1/admin/channels`, `GET .../statistics`.
- Dashboard menu: Join Requests → **Channels** → Analytics → AI Usage → AI Settings.
- Enable/Disable channel — inactive channels ignore new join requests; history preserved.
- Channel registration saves `username` and creates default settings.
- Channel timeline: join requests + AI cost + accuracy (7/30/90 days).
- Documentation: `docs/channel_management.md`, `docs/api.md`; updated `dashboard.md`, `architecture.md`.
- Tests: channels service, API, web, repository, inactive channel processing.

### Not changed (by design)

- Rule Engine, AI Gateway, OpenRouter, Reputation Engine logic
- Join Pipeline decision flow (except `is_active` guard)
- Global Analytics (`/admin/analytics`)

---

## [1.7.0] — 2026-06-30

### Added

- **AI Analytics & Feedback Center** — `/admin/analytics` with accuracy, decision distribution, provider stats, rule effectiveness, feedback categories, timeline (7/30/90 days), recent 50 cases.
- `AnalyticsRepository` + `AnalyticsService` — aggregated SQL, no SQL in routers.
- REST API (read-only): `/api/v1/admin/analytics`, `/accuracy`, `/rules`, `/providers`, `/timeline`.
- Extended `/admin/ai`: today/month cost, avg tokens, most used/accurate/expensive model.
- **Decision Inspector** on join request detail — AI vs Human with verdict.
- Documentation: `docs/analytics.md`; updated `dashboard.md`, `architecture.md`.
- Tests: analytics service, API, dashboard, accuracy, rules, providers.

### Not changed (by design)

- Join Request pipeline
- Rule Engine, Feature Extraction, Reputation Engine
- AI Gateway / OpenRouterProvider

---

## [1.6.0] — 2026-06-30

### Added

- **Hybrid Explainability** — `HybridExplainabilityBuilder` объединяет системные и AI-сигналы.
- Deterministic positive signals: фото, username, Premium, репутация ≥ 70, rule score 0.
- Deterministic negative signals: сработавшие правила, цифры в username, крипто/random username, низкая репутация ≤ 40.
- Merge с GPT `positive_signals` / `negative_signals` без дубликатов; AI-минусы фильтруются при конфликте с системными плюсами.
- Цветовая шкала AI Risk Score: 🟢 0–29 · 🟡 30–69 · 🔴 70–100 с маркером и badge.
- Dashboard: колонки «🟢 Положительные признаки» / «🔴 Факторы риска»; hybrid-сигналы при `AI SKIPPED`.

### Not changed (by design)

- Rule Engine logic
- Database models / migrations
- Decision Engine business logic

---

## [1.5.0] — 2026-06-30

### Added

- **Explainable AI** — расширенный JSON-ответ GPT: `risk_score`, `confidence`, `reason`, `recommended_action`, `positive_signals`, `negative_signals`, `short_summary`.
- Сохранение explainable-полей в существующем `ai_analyses.explanation` → `ai_result` (без новых таблиц и миграций).
- Dashboard detail: блок **Explainable AI** — резюме, индикатор уверенности, «Почему принято такое решение», цветные positive/negative signals.
- Обратная совместимость: legacy `signals` отображаются как negative factors.
- `ExplainableAIDTO` и маппинг в `AdminDashboardService`.
- Обновлены OpenRouter/OpenAI/Mock providers и prompt instructions (ответ на русском, где возможно).

### Not changed (by design)

- Rule Engine
- Database models / migrations
- Decision Engine business logic
- Reputation Engine

---

## [1.4.0] — 2026-06-30

### Added

- **OpenRouterProvider** — универсальный AI Gateway через HTTP API (httpx).
- **AIRouter** — выбор provider по `AI_PROVIDER` (mock / openrouter / openai).
- Настройки: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`, `AI_TIMEOUT`, `AI_MAX_RETRIES`.
- Поддержка моделей через `.env` без изменения кода (GPT-4.1, Claude, Gemini, DeepSeek, Llama).
- Расширенный `PromptBuilder`: rule score, trust score, signals, summary, reputation history (без PII).
- Расширенный `StructuredAnalysisOutput`: risk_score, recommended_action, signals.
- Таблица `ai_usage` — provider, model, tokens, cost, latency.
- Dashboard: `/admin/ai` (статистика), `/admin/settings/ai` (read-only конфиг).
- AI Status: Success / Fallback / Failed.
- Документация: `docs/openrouter.md`.
- Unit + integration tests для OpenRouter, AIRouter, retry, timeout, fallback, ai_usage.

### Not changed (by design)

- Rule Engine
- Reputation Engine
- Decision Engine business logic
- OpenAI SDK provider (legacy, optional)

---

## [1.3.0] — 2026-06-30

### Added

- **Reputation Engine** (`app/reputation/`): `ReputationEngine`, `ReputationService`.
- `trust_score` (0–100, default 50) в `reputations.reputation_score`.
- Таблица `reputation_history` — audit trail изменений репутации.
- Join pipeline: trust ≥ 90 → auto APPROVED; trust ≤ 10 → auto REJECTED (без Rule Engine и AI).
- Admin actions обновляют репутацию: Approve +5, Reject −10, Whitelist 100, Blacklist 0.
- `RiskProfile.trust_score` — поле для будущего учёта AI (builder algorithm unchanged).
- Dashboard: колонка Trust, карточка Avg Trust, Trust Score на detail, Reputation History.
- REST API: `GET /api/v1/admin/reputation/{telegram_user_id}` (current_score, history, trend).
- Trend: UP / DOWN / STABLE по последним изменениям.
- Документация: `docs/reputation.md`, обновлены architecture, dashboard, join_request_processing.
- Unit + integration tests для reputation, auto approve/reject, dashboard, API.

### Not changed (by design)

- OpenAI / AI Layer algorithm
- Rule Engine
- Feature Extraction
- AI Feedback table/logic

---

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
