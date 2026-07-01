# BotHunter AI — REST API

Base URL: `/api/v1`

OpenAPI: `/docs`

---

## Admin — Investigations (v1.9)

Prefix: `/admin/investigations`

| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List investigations |
| GET | `/{id}` | Case detail |
| GET | `/{id}/timeline` | Decision timeline |
| GET | `/{id}/export?format=json\|pdf` | Export case |
| POST | `/{id}/replay` | Replay AI analysis |

See [docs/investigation_center.md](investigation_center.md).

---

## Admin — Channels (v1.8)

Prefix: `/admin/channels`

| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List all channels |
| GET | `/{channel_id}` | Channel detail + settings + timeline |
| GET | `/{channel_id}/statistics` | Aggregated statistics |
| PATCH | `/{channel_id}` | Update settings / `is_active` |

See [docs/channel_management.md](channel_management.md) for payload examples.

---

## Admin — Join Requests

Prefix: `/admin`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/join-requests` | Paginated list |
| GET | `/join-requests/{id}` | Detail |
| GET | `/statistics` | Dashboard stats |
| POST | `/join-requests/{id}/approve` | Approve |
| POST | `/join-requests/{id}/reject` | Reject |

---

## Admin — Analytics (v1.7)

Prefix: `/admin/analytics`

| Method | Path | Description |
|--------|------|-------------|
| GET | `` | Overview |
| GET | `/timeline?days=7\|30\|90` | AI quality timeline |
