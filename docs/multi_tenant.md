# BotHunter AI — Multi-Tenant Architecture (v3.0)

BotHunter AI v3.0 introduces organization-scoped SaaS infrastructure. Each customer operates inside an **Organization** with one or more **Workspaces**. Data, policies, billing, and secrets are isolated per organization.

## Core Concepts

| Entity | Description |
|--------|-------------|
| **Organization** | Top-level tenant. Has a plan (Free, Starter, Professional, Enterprise), branding, and secrets. |
| **Workspace** | Sub-scope inside an organization. Join requests and channels are filtered by active workspace. |
| **Organization Member** | Dashboard user linked to an organization with a role (Owner, Admin, Viewer, …). |
| **Workspace Member** | Dashboard user linked to a specific workspace. |

## Tenant Context

Every authenticated dashboard/API request resolves a `TenantContext`:

- `organization_id` — active organization (session or `X-Organization-Id` header)
- `workspace_id` — active workspace (session or `X-Workspace-Id` header)

Use the navbar **Switch** dropdown to change workspace. The navbar shows the current organization and workspace badges.

## Organization Management (Phase 2)

### Members — `/admin/organization/members`

Lists organization members with name, email, role, workspaces, status, and last login. Owners can invite users by email, role, and workspace. Invites generate a token link:

```
/invite/{token}
```

Email delivery is not implemented yet; copy the invite URL from the UI or API response.

### Accept Invite — `/invite/{token}`

Invitees set their name and password, then receive a dashboard session.

### Secrets — `/admin/organization/secrets`

Per-organization secrets (masked in UI):

- OpenRouter API Key
- Telegram Bot Token
- Webhook Secret

Values are stored in `organization_secrets` and displayed as `********abcd`.

**Runtime:** The join pipeline uses the organization's OpenRouter key when configured; otherwise it falls back to the global `.env` key.

### Billing — `/admin/billing`

Shows current plan, usage, limits, and remaining quota for:

- AI Requests
- LLM Tokens
- Channels
- Users
- Storage (estimated)

### White Label — `/admin/organization/branding`

Configure logo URL, brand color, display name, and favicon. Brand color and display name appear in the admin navbar.

## Plan Limits

| Plan | Channels |
|------|----------|
| Free | 1 |
| Starter | 5 |
| Professional | 20 |
| Enterprise | Unlimited |

Channel registration and invite acceptance enforce these limits. Exceeding a limit returns an error.

## REST API

All endpoints require dashboard session authentication.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/organization` | Current organization |
| PATCH | `/api/v1/organization` | Update organization (Owner/Admin) |
| GET | `/api/v1/organization/members` | List members |
| POST | `/api/v1/organization/invite` | Create invite |
| GET | `/api/v1/organization/secrets` | List masked secrets |
| POST | `/api/v1/organization/secrets` | Upsert a secret |
| GET | `/api/v1/billing` | Billing dashboard |

## Database

Key tables:

- `organizations`, `workspaces`
- `organization_members`, `workspace_members`
- `organization_invites`, `organization_secrets`, `organization_usage`

Tenant foreign keys exist on `telegram_channels`, `policy_versions`, `audit_logs`, `ai_usage`, and related entities.

Migrations:

- `i9j0k1l2m3n4` — Phase 1 multi-tenant foundation
- `j0k1l2m3n4o5` — Phase 2 org management (favicon, invite workspace)

## Bootstrap

On startup, `TenantBootstrapService` ensures a default organization and workspace, backfills legacy rows, and seeds the initial policy for that organization.

## Out of Scope (Phase 2)

The following remain global or unchanged in Phase 2:

- Rule Engine logic
- AI provider implementation (only key resolution is tenant-aware)
- Reputation, Investigation, Analytics engines

Phase 3 will complete full tenant scoping across remaining modules.

## Version

**v3.0.0-beta** — Organization management complete (Phase 2).
