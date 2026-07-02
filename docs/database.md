# BotHunter AI — Database

## Обзор

Доменная модель v0.2 описывает сущности платформы BotHunter AI для управления Telegram-ботами, каналами, заявками на вступление, AI-анализом, репутацией и списками доступа.

Стек:

- PostgreSQL 16
- SQLAlchemy 2.0
- Alembic
- UUID (первичные ключи)
- PostgreSQL ENUM

---

## Таблицы

| Таблица | Описание |
|---------|----------|
| `users` | Пользователи платформы |
| `telegram_bots` | Telegram-боты, принадлежащие пользователям |
| `telegram_channels` | Подключённые Telegram-каналы |
| `telegram_users` | Пользователи Telegram, проходившие проверку |
| `join_requests` | История заявок на вступление в канал |
| `ai_analyses` | История AI-анализа заявок |
| `reputations` | Репутация Telegram-пользователя |
| `blacklists` | Чёрный список |
| `whitelists` | Белый список |
| `audit_logs` | Аудит действий |

---

## ER Diagram

```mermaid
erDiagram
    users ||--o{ telegram_bots : owns
    users ||--o{ telegram_channels : owns
    users ||--o{ whitelists : approves

    telegram_bots ||--o{ telegram_channels : manages

    telegram_channels ||--o{ join_requests : receives

    telegram_users ||--o{ join_requests : submits
    telegram_users ||--o| reputations : has
    telegram_users ||--o{ blacklists : listed_in
    telegram_users ||--o{ whitelists : listed_in

    join_requests ||--o{ ai_analyses : analyzed_by

    users {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        bigint telegram_id UK
        timestamptz created_at
        timestamptz updated_at
    }

    telegram_bots {
        uuid id PK
        uuid owner_id FK
        string bot_token
        string bot_username UK
        timestamptz created_at
    }

    telegram_channels {
        uuid id PK
        uuid owner_id FK
        uuid bot_id FK
        bigint telegram_chat_id UK
        string title
        string invite_link
        boolean is_active
        timestamptz created_at
    }

    telegram_users {
        uuid id PK
        bigint telegram_id UK
        string username
        string first_name
        string last_name
        string language_code
        boolean is_premium
        boolean has_photo
        timestamptz created_at
        timestamptz updated_at
    }

    join_requests {
        uuid id PK
        uuid channel_id FK
        uuid telegram_user_id FK
        enum status
        timestamptz created_at
    }

    ai_analyses {
        uuid id PK
        uuid join_request_id FK
        float rule_score
        float ai_score
        float final_score
        enum decision
        text explanation
        timestamptz created_at
    }

    reputations {
        uuid id PK
        uuid telegram_user_id FK UK
        float reputation_score
        int bot_votes
        int human_votes
        timestamptz last_update
    }

    blacklists {
        uuid id PK
        uuid telegram_user_id FK
        text reason
        float confidence
        string source
        timestamptz created_at
    }

    whitelists {
        uuid id PK
        uuid telegram_user_id FK
        uuid approved_by FK
        timestamptz created_at
    }

    audit_logs {
        uuid id PK
        string actor
        string action
        string entity
        uuid entity_id
        timestamptz created_at
    }
```

---

## Связи (ForeignKey)

| Таблица | Поле | Ссылается на | ON DELETE |
|---------|------|--------------|-----------|
| `telegram_bots` | `owner_id` | `users.id` | CASCADE |
| `telegram_channels` | `owner_id` | `users.id` | CASCADE |
| `telegram_channels` | `bot_id` | `telegram_bots.id` | CASCADE |
| `join_requests` | `channel_id` | `telegram_channels.id` | CASCADE |
| `join_requests` | `telegram_user_id` | `telegram_users.id` | CASCADE |
| `ai_analyses` | `join_request_id` | `join_requests.id` | CASCADE |
| `reputations` | `telegram_user_id` | `telegram_users.id` | CASCADE |
| `blacklists` | `telegram_user_id` | `telegram_users.id` | CASCADE |
| `whitelists` | `telegram_user_id` | `telegram_users.id` | CASCADE |
| `whitelists` | `approved_by` | `users.id` | SET NULL |

---

## Unique Constraints

| Таблица | Поля | Имя ограничения |
|---------|------|-----------------|
| `users` | `email` | `uq_users_email` |
| `users` | `telegram_id` | `uq_users_telegram_id` |
| `telegram_bots` | `bot_username` | `uq_telegram_bots_bot_username` |
| `telegram_channels` | `telegram_chat_id` | `uq_telegram_channels_telegram_chat_id` |
| `telegram_users` | `telegram_id` | `uq_telegram_users_telegram_id` |
| `reputations` | `telegram_user_id` | `uq_reputations_telegram_user_id` |

---

## Индексы

| Таблица | Индекс | Поля |
|---------|--------|------|
| `users` | `ix_users_email` | `email` |
| `users` | `ix_users_telegram_id` | `telegram_id` |
| `telegram_bots` | `ix_telegram_bots_owner_id` | `owner_id` |
| `telegram_bots` | `ix_telegram_bots_bot_username` | `bot_username` |
| `telegram_channels` | `ix_telegram_channels_owner_id` | `owner_id` |
| `telegram_channels` | `ix_telegram_channels_bot_id` | `bot_id` |
| `telegram_channels` | `ix_telegram_channels_telegram_chat_id` | `telegram_chat_id` |
| `telegram_channels` | `ix_telegram_channels_is_active` | `is_active` |
| `telegram_users` | `ix_telegram_users_telegram_id` | `telegram_id` |
| `telegram_users` | `ix_telegram_users_username` | `username` |
| `join_requests` | `ix_join_requests_channel_id` | `channel_id` |
| `join_requests` | `ix_join_requests_telegram_user_id` | `telegram_user_id` |
| `join_requests` | `ix_join_requests_status` | `status` |
| `join_requests` | `ix_join_requests_channel_user_created` | `channel_id`, `telegram_user_id`, `created_at` |
| `ai_analyses` | `ix_ai_analyses_join_request_id` | `join_request_id` |
| `ai_analyses` | `ix_ai_analyses_decision` | `decision` |
| `ai_analyses` | `ix_ai_analyses_created_at` | `created_at` |
| `reputations` | `ix_reputations_telegram_user_id` | `telegram_user_id` |
| `reputations` | `ix_reputations_reputation_score` | `reputation_score` |
| `blacklists` | `ix_blacklists_telegram_user_id` | `telegram_user_id` |
| `blacklists` | `ix_blacklists_source` | `source` |
| `blacklists` | `ix_blacklists_created_at` | `created_at` |
| `whitelists` | `ix_whitelists_telegram_user_id` | `telegram_user_id` |
| `whitelists` | `ix_whitelists_approved_by` | `approved_by` |
| `whitelists` | `ix_whitelists_created_at` | `created_at` |
| `audit_logs` | `ix_audit_logs_actor` | `actor` |
| `audit_logs` | `ix_audit_logs_action` | `action` |
| `audit_logs` | `ix_audit_logs_entity` | `entity` |
| `audit_logs` | `ix_audit_logs_entity_id` | `entity_id` |
| `audit_logs` | `ix_audit_logs_created_at` | `created_at` |
| `audit_logs` | `ix_audit_logs_entity_entity_id` | `entity`, `entity_id` |

---

## ENUM-типы

### `join_request_status`

- `Pending`
- `Approved`
- `Rejected`
- `ManualReview`

### `analysis_decision`

- `Approved`
- `Rejected`
- `ManualReview`

---

## Миграции

Текущая head-ревизия: `657650f1297c` — `create_domain_models_v0_2`

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

В Docker:

```bash
docker exec bothunter-api alembic upgrade head
```

---

## Расположение моделей

```
backend/app/models/
├── __init__.py
├── enums.py
├── mixins.py
├── user.py
├── telegram_bot.py
├── telegram_channel.py
├── telegram_user.py
├── join_request.py
├── ai_analysis.py
├── reputation.py
├── blacklist.py
├── whitelist.py
└── audit_log.py
```

---

## Backup

### Резервная копия перед релизом / go-live

Скрипты (из корня репозитория):

```powershell
# Windows (Docker Desktop)
.\scripts\backup_database.ps1
```

```bash
# Linux / macOS
./scripts/backup_database.sh
```

Дампы сохраняются в `backups/` с именем `bothunter_YYYYMMDD_HHMMSS.sql` (каталог в `.gitignore`).

Требования: контейнер `bothunter-postgres` запущен (`docker compose -f docker/docker-compose.yml up -d`).

### Ручной pg_dump

```bash
docker exec bothunter-postgres pg_dump -U bothunter bothunter > backups/bothunter_manual.sql
```

### Dashboard Backup (JSON/SQL/CSV)

Админ-панель v2.0+: **Settings → Backup/Restore** — экспорт конфигурации и данных без прямого доступа к PostgreSQL.

### Восстановление

```bash
docker exec -i bothunter-postgres psql -U bothunter -d bothunter < backups/bothunter_YYYYMMDD_HHMMSS.sql
```

Перед restore на production — остановите API/bot и сделайте второй backup текущего состояния.
