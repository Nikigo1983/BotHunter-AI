# BotHunter AI — REST API

Base URL: `/api/v1`

OpenAPI: `/docs`

---

## Admin — Policies (v2.1)

Prefix: `/admin/policies`

| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List all rules + current version |
| GET | `/{rule_key}` | Single rule detail |
| PATCH | `/{rule_key}` | Update rule (creates new version) |
| GET | `/thresholds` | Current global thresholds |
| PATCH | `/thresholds` | Update thresholds |
| POST | `/simulate` | Simulate rule/threshold change |
| POST | `/rollback` | Rollback to policy version |
| GET | `/history` | Policy version history |
| GET | `/compare` | Compare current vs previous |

See [docs/policy_center.md](policy_center.md).

---

## Admin — Investigations (v1.9)

Prefix: `/admin/investigations`

| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List investigations |
| GET | `/{id}` | Case detail |
| GET | `/{id}/timeline` | Decision timeline |
| GET | `/{id}/export?format=json\|pdf` | Export case |
| POST | `/{id}/replay` | Replay AI analysis (optional `policy_version_id`) |

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
