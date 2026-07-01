# BotHunter AI — Investigation Center (v1.9)

## Overview

Investigation Center turns every Join Request into a full investigation case with decision timeline, prompt/response viewers, rule inspection, exports, and replay — without changing Rule Engine, AI Gateway, Reputation Engine, or Join Pipeline.

## Web UI

| URL | Description |
|-----|-------------|
| `/admin/investigations` | Case list with filters |
| `/admin/join-request/{id}` | Case detail + Investigation Center blocks |

### Menu order

Join Requests → **Investigations** → Channels → Analytics → AI Usage → AI Settings

### Filters

Channel, Status, AI Decision, Human Decision, Trust/Rule/AI score ranges, date range, search (Telegram ID, username, first/last name).

### Case detail blocks

- **Decision Comparator** — Rule Engine → AI → Final → Human
- **Decision Timeline** — staged pipeline with time and duration
- **Rule Inspector** — condition, matched, contribution per rule
- **Prompt** — system + user prompt (secrets redacted)
- **AI Response Viewer** — parsed + raw JSON
- **Audit Log** — admin actions including replay/export
- **Export JSON / Export PDF**
- **Replay Analysis** — re-runs AI path without DB/Telegram changes

## REST API

Prefix: `/api/v1/admin/investigations`

| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List investigations |
| GET | `/{id}` | Full case |
| GET | `/{id}/timeline` | Timeline only |
| GET | `/{id}/export?format=json\|pdf` | Download case |
| POST | `/{id}/replay` | Replay AI analysis |

## Architecture

- `InvestigationRepository` — filtered list, audit fetch
- `InvestigationService` — timeline, prompt, replay, export, audit writes
- `RuleInspector` — rule conditions without changing Rule Engine
- `TimelineBuilder` — decision path reconstruction
- `investigation/export.py` — JSON + PDF generation

## Audit

`audit_logs.details` (JSON text) stores metadata for:

- `replay`
- `export_json`
- `export_pdf`

Existing approve/reject/whitelist/blacklist actions continue to write audit rows.

## Database

Migration `f6a7b8c9d0e1` adds `audit_logs.details`.
