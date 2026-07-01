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

## Version

**v3.0.0** — Full multi-tenant SaaS (Phase 3 complete).

---

## Phase 3 — SaaS Completion (v3.0.0)

### Organization Management — `/admin/organizations`

Owners can create, update, archive, and delete organizations (delete blocked when channels or multiple members exist). New organizations start with `onboarding_completed=false` and redirect to the onboarding wizard.

### Workspace Management — `/admin/workspaces`

Owners can create workspaces, rename, archive (except default), and assign organization members to workspaces with roles.

### Analytics Tenant Scope

All analytics queries filter by active `organization_id` and `workspace_id`:

- Dashboard statistics (via tenant-scoped join request repo)
- Investigation Center
- AI Usage (`/admin/ai`)
- Billing metrics
- Rule Analytics (Policy Center)
- Provider Analytics

### Organization Telegram Runtime

`TelegramRuntimeService` resolves the organization's Telegram bot token from secrets; falls back to global `BOT_TOKEN`. Used in join-request actions and channel registration verification.

### Onboarding Wizard — `/admin/onboarding`

Steps: organization name → plan → workspace → Telegram token → OpenRouter key → first channel → connection verify → done.

### Release Validation — `/admin/release-check`

Green **Ready for Production** banner when all nine checks pass.

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
- `k1l2m3n4o5p6` — Phase 3 SaaS completion (archive flags, onboarding)

## Bootstrap

On startup, `TenantBootstrapService` ensures a default organization and workspace, backfills legacy rows, and seeds the initial policy for that organization.

## Out of Scope (unchanged engines)

Rule Engine logic, AI provider implementation, Reputation engine core — only tenant-scoped configuration and data access changed in v3.0.

## Version

**v3.0.0** — Full SaaS release (Phase 3 complete).
