# BotHunter AI — Changelog

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
