# BotHunter AI v3.0.0 — Release Notes

**Release date:** 2026-06-30  
**Git tag:** `v3.0.0`

---

## Highlights

BotHunter AI v3.0.0 completes the **multi-tenant SaaS platform** and adds **account-age / phone-linkage risk signals** to the Rule Engine for stronger spam detection on fresh Telegram profiles.

---

## Multi-Tenant SaaS (Phase 3)

- **Organization Management** — `/admin/organizations` (create, update, archive, delete; Owner only)
- **Workspace Management** — `/admin/workspaces` (create, rename, archive, member assignment)
- **Onboarding Wizard** — `/admin/onboarding` (8 steps: org, plan, workspace, Telegram, OpenRouter, channel, verify, done)
- **Release Validation** — `/admin/release-check` (Database, Redis, Telegram, OpenRouter, Billing, Workspace, Organization, AI, Analytics)
- **Tenant-scoped Analytics & Investigations** — filtered by `organization_id` + `workspace_id`
- **Organization Telegram runtime** — org bot token with global fallback
- Migration `k1l2m3n4o5p6` (`is_archived`, `onboarding_completed`)

## Multi-Tenant Foundation (Phase 1–2, included in v3.0.0)

- Organizations, Workspaces, tenant context, plan limits, billing dashboard
- Members, invites, secrets, white-label branding, REST API
- See [multi_tenant.md](multi_tenant.md)

---

## Rule Engine — Account Age & Phone Heuristics

Two new deterministic rules (11 rules total):

| Rule | Default score | Trigger |
|------|--------------:|---------|
| `AccountCreatedTodayRule` | **+35** | Estimated Telegram registration date = today (User ID interpolation) |
| `NoLinkedPhoneRule` | **+15** | Heuristic: likely no linked phone (Bot API does not expose phone status) |

### Tuned behavior

- **Account created today alone** → rule score **35** → **Manual Review** (threshold 30)
- **Today + likely no phone** → **50** → Manual Review (not auto-reject)
- Weights editable in **Policy Center** (`/admin/policies`)

### Configurable heuristics (`backend/config/decision_thresholds.yaml`)

```yaml
telegram_account_heuristics:
  no_phone_inference_max_age_days: 45
  linked_phone_assumed_min_age_days: 120
```

Optional env overrides: `TELEGRAM_NO_PHONE_MAX_AGE_DAYS`, `TELEGRAM_LINKED_PHONE_MIN_AGE_DAYS`.

**Note:** Registration date and phone linkage are **estimates**, not facts from Telegram Bot API.

---

## Upgrade

```bash
docker compose -f docker/docker-compose.yml pull
docker compose -f docker/docker-compose.yml up -d --build
docker exec bothunter-api alembic upgrade head
docker exec bothunter-api python -m pytest -q
```

Before production go-live:

- Rotate `DASHBOARD_SESSION_SECRET`, admin password, `POSTGRES_PASSWORD`
- Enable HTTPS cookies (`DASHBOARD_HTTPS_ENABLED`, `DASHBOARD_COOKIE_SECURE`)
- Configure org or global Telegram / OpenRouter secrets
- Run `/admin/release-check` → **Ready for Production**
- Take a database backup (see [database.md](database.md#backup))

---

## Default login (first bootstrap)

- Email: `admin@bothunter.local`
- Password: `admin` (change immediately)

---

## Recommended next step

Deploy to 2–3 test Telegram channels, collect real join-request cases for 2–4 weeks, then plan **v3.1** from operator feedback — not feature lists.

---

## Documentation

- [Changelog](changelog.md)
- [Release Checklist v3.0](release_checklist_v3.0.md)
- [Rule Engine](rule_engine.md)
- [Feature Extraction](features.md)
- [Multi-Tenant Architecture](multi_tenant.md)
