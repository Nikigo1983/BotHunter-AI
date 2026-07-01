# BotHunter AI v3.0.0 — Release Checklist

**Final release audit:** 2026-06-30  
**Git tag:** `v3.0.0`  
**Tests:** 214 passed (Docker)

---

## Executive Summary

| Area | v3.0.0-beta | v3.0.0 |
|------|-------------|--------|
| Default org bootstrap | PASS | PASS |
| Self-service org/workspace | PARTIAL | **PASS** |
| Analytics tenant scope | GAP | **PASS** |
| Investigation tenant scope | GAP | **PASS** |
| Org Telegram runtime | PARTIAL | **PASS** |
| Onboarding wizard | — | **PASS** |
| Release validation page | — | **PASS** |
| Security isolation tests | Partial | **PASS** |

**Verdict:** v3.0.0 is approved for production deployment with standard env hardening (see §6).

---

## 1. Secrets Scan — PASS

No production credentials in git. `.env` gitignored. Test fixtures use fake keys only.

---

## 2. `.gitignore` — PASS

`.env`, venv, logs, caches, local DB files covered.

---

## 3. Alembic Migrations — PASS

**Head:** `k1l2m3n4o5p6`

```
657650f1297c → … → j0k1l2m3n4o5 → k1l2m3n4o5p6
```

Fresh DB `alembic upgrade head` verified.

---

## 4. Bootstrap (Fresh DB) — PASS

| Item | Result |
|------|--------|
| Owner | `admin@bothunter.local` |
| Default Organization | slug `default` |
| Default Workspace | slug `default` |
| Policy v1 | version 1 |

---

## 5. Onboarding Flows — PASS

| Flow | Status |
|------|--------|
| Create Organization (Owner) | `/admin/organizations` |
| Create Workspace | `/admin/workspaces` |
| Onboarding wizard | `/admin/onboarding` (8 steps) |
| Invite user | Phase 2 flow |
| Connect channel | Org-scoped + plan limits |
| Join request + AI | Org OpenRouter + org Telegram |
| Dashboard | Tenant-scoped |
| Analytics | Tenant-scoped |

---

## 6. Production Checklist

```bash
docker exec bothunter-api alembic upgrade head
docker exec bothunter-api python -m pytest -q
# Expected: 214 passed
```

Before go-live:

- [ ] Rotate `DASHBOARD_SESSION_SECRET`
- [ ] Rotate `DASHBOARD_ADMIN_PASSWORD` and `POSTGRES_PASSWORD`
- [ ] Set `DASHBOARD_HTTPS_ENABLED=true` + `DASHBOARD_COOKIE_SECURE=true`
- [ ] Configure org secrets or global `BOT_TOKEN` / `OPENROUTER_API_KEY`
- [ ] Complete `/admin/onboarding` for each new organization
- [ ] Verify `/admin/release-check` shows **Ready for Production**

---

## 7. Security Review — PASS

| Check | Coverage |
|-------|----------|
| Tenant isolation (join requests) | `test_tenant_isolation.py` |
| Tenant isolation (analytics) | `test_phase3_saas.py` |
| Tenant isolation (investigations) | `test_phase3_saas.py` |
| Cross-org access blocked | Owner-only org management |
| Secrets masking | Phase 2 tests |
| Role escalation | Viewer blocked from `/admin/organizations` |

---

## 8. Phase 3 Deliverables

- [x] `/admin/organizations`
- [x] `/admin/workspaces`
- [x] Analytics tenant scope
- [x] Organization Telegram runtime
- [x] Onboarding wizard
- [x] `/admin/release-check`
- [x] Security tests
- [x] Documentation updated

---

## 9. Post-Release Recommendation

After v3.0.0: **feedback-driven development**.

1. Connect 2–3 test Telegram channels.
2. Collect real join-request cases for 2–4 weeks.
3. Plan v3.1 from observed false positives, policy gaps, and operator workflow — not feature lists.

---

## References

- [Multi-Tenant Architecture](multi_tenant.md)
- [Production Readiness](production_readiness.md)
- [Changelog](changelog.md)
