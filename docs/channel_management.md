# BotHunter AI — Channel Management

## Обзор

**v1.8** добавляет центр управления несколькими Telegram-каналами через Admin Dashboard и REST API.

Все настройки канала хранятся в PostgreSQL (`channel_settings`). Изменение `.env` для порогов канала **не требуется**.

---

## Web UI

| URL | Описание |
|-----|----------|
| `/admin/channels` | Список всех подключённых каналов со статистикой |
| `/admin/channels/{id}` | Карточка канала: info, stats, timeline, settings, последние 20 заявок |

### Порядок меню Dashboard

1. Join Requests  
2. **Channels**  
3. Analytics  
4. AI Usage  
5. AI Settings  

### Enable / Disable Channel

- **Disable** — бот перестаёт обрабатывать новые Join Requests канала (`is_active = false`)
- **Enable** — обработка возобновляется
- История, аналитика и AI Usage **не удаляются**

---

## REST API

См. [docs/api.md](api.md).

---

## Repositories

| Repository | Назначение |
|------------|------------|
| `ChannelRepository` | CRUD канала, enable/disable |
| `ChannelSettingsRepository` | `channel_settings`, get_or_create с defaults |
| `ChannelStatisticsRepository` | SQL-агрегации, timeline, recent requests |

---

## Database

Миграция: `e5f6a7b8c9d0_add_channel_settings_v1_8`.
