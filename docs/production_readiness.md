# BotHunter AI v2.0 — Production Readiness

## Dashboard authentication

- Login: `/admin/login`
- Logout: `/admin/logout`
- Session cookie: `bothunter_session` (HttpOnly, SameSite=Lax)
- Password hashing: bcrypt via `passlib`
- CSRF token on all admin POST forms
- Default owner created on first startup from env:
  - `DASHBOARD_ADMIN_EMAIL` (default `admin@bothunter.local`)
  - `DASHBOARD_ADMIN_PASSWORD` (default `admin`)

## Roles

| Role | Permissions |
|------|-------------|
| Owner | Full access including user management |
| Administrator | Settings, backup, secrets, moderation |
| Moderator | Join actions, channels (no global AI settings) |
| Viewer | Read-only dashboard |

## Settings UI

`/admin/settings` — edit AI provider, model, timeout, retry, thresholds, monthly budget without changing `.env`. API keys remain in environment variables.

## System monitor

`/admin/system` — health checks, production ready score, usage, Docker/host metrics.

Sub-pages:

- `/admin/system/errors` — Error Center
- `/admin/system/queue` — Queue monitor
- `/admin/system/usage` — Usage limits
- `/admin/system/backup` — Backup / restore
- `/admin/system/secrets` — Masked secrets
- `/admin/system/logs` — Log viewer
- `/admin/system/notifications` — Alert center

## Production Ready checklist

The score on `/admin/system` reflects:

- AI configured
- Telegram connected
- Channel connected
- OpenRouter working
- Redis / PostgreSQL
- Dashboard auth enabled
- HTTPS (`DASHBOARD_HTTPS_ENABLED`)
- Backup configured
- Monitoring

## Migration

```bash
alembic upgrade head
```

Revision: `g7h8i9j0k1l2` — dashboard auth, system settings, errors, notifications.
