# BotHunter AI — Policy Center (v2.1)

## Overview

Policy Center makes the Rule Engine **fully manageable from the Dashboard** without changing Python code.

Administrators can edit rule scores, enable/disable rules, global thresholds, simulate impact, version every change, rollback, and replay investigations against historical policies.

## Web UI

| URL | Description |
|-----|-------------|
| `/admin/policies` | All rules with analytics (triggered, accuracy, FP, last change) |
| `/admin/policies/{rule}` | Rule editor + simulator |
| `/admin/policies/thresholds` | Approve / Manual Review / Reject / Trust / AI thresholds |
| `/admin/policies/history` | Policy versions with rollback |
| `/admin/policies/compare` | Current vs previous policy diff |

Menu order: Join Requests → Investigations → Channels → **Policies** → Analytics → AI Usage → Settings → System.

## Architecture

```mermaid
flowchart LR
    Dashboard[Policy Center UI] --> PolicyRouter[admin/policy_router]
    API[/api/v1/admin/policies] --> PolicyService
    PolicyRouter --> PolicyService
    PolicyService --> PolicyRepository[(policy_versions)]
    PolicySimulationService --> PolicyRepository
    PolicySimulationService --> JoinCases[(join_requests)]
    JoinPipeline[JoinRequestProcessingService] --> PolicyService
    InvestigationReplay[InvestigationService.replay] --> PolicyService
    PolicyService --> RuleEngine[RuleEngine from policy snapshot]
    PolicyService --> DecisionEngine[DecisionEngine from thresholds]
```

### Components

| Component | Role |
|-----------|------|
| `PolicyRepository` | CRUD for versions, rule snapshots, threshold snapshots |
| `PolicyService` | Effective policy resolution, edits, rollback, compare, analytics merge |
| `PolicySimulationService` | Dry-run on last N join requests (default 100) |
| `policy/types.py` | `EffectivePolicy`, `RulePolicyConfig`, `PolicyThresholdConfig` |

### Database

| Table | Purpose |
|-------|---------|
| `policy_versions` | Version metadata (author, comment, is_current) |
| `policy_rule_configs` | Per-version rule score/enabled/description |
| `policy_threshold_configs` | Per-version global thresholds |

Migration: `h8i9j0k2l3m4_v2_1_policy_center.py`

Initial policy **v1** is seeded on startup from Rule Engine defaults (`ensure_initial_policy`).

## Rule Editor

Editable fields per rule:

- **Score** (0–100)
- **Enabled**
- **Description**
- **Admin comment**

Each save creates a new policy version.

## Rule Simulator

Before saving, simulate how the last 100 join requests would be decided:

```
Approve     +18
Reject      −6
Manual      −12
```

Nothing is written to the database during simulation.

## Policy Versioning

Every rule or threshold change creates **Policy vN** with:

- Date, author, comment
- Changed rules list (vs previous version)

**Rollback** copies a historical snapshot into a **new** current version (audit-friendly).

## Decision Replay

In Investigation Center (`/admin/join-request/{id}`):

- **Current Policy** — default replay
- **Policy vN** — replay with historical rule/threshold snapshot

Replay does not modify join request status or Telegram state.

## Global Threshold Editor

Editable via `/admin/policies/thresholds`:

| Field | Default |
|-------|---------|
| `approve_below` | 30 |
| `reject_from` | 70 |
| `trust_auto_approve` | 90 |
| `trust_auto_reject` | 10 |
| `ai_threshold` | 0.75 |

Stored in `policy_threshold_configs`, not `.env`.

## Rule Analytics

Per-rule metrics reuse existing Analytics + Investigation data:

- Accuracy, Precision, Recall
- False Positive Rate, False Negative Rate
- Triggered count, false positives

## REST API

Prefix: `/api/v1/admin/policies`

| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List all rules + current version |
| GET | `/{rule_key}` | Single rule |
| PATCH | `/{rule_key}` | Update rule (creates version) |
| GET | `/thresholds` | Current thresholds |
| PATCH | `/thresholds` | Update thresholds |
| POST | `/simulate` | Dry-run simulation |
| POST | `/rollback` | Rollback to version snapshot |
| GET | `/history` | Version list |
| GET | `/compare` | Current vs previous diff |

Requires dashboard session auth. Edits require **Owner** or **Administrator** (`change_system_settings`).

## Permissions

Same as System Settings: `PERMISSION_CHANGE_SYSTEM_SETTINGS`.

Moderator and Viewer can browse policies; they cannot save or rollback.

## Not changed (by design)

- Telegram Bot handlers
- AI Gateway / OpenRouterProvider
- Repository layer pattern (Policy adds new repositories only)
- Authentication
- Investigation Center structure (minimal replay policy selector added)

## Tests

`tests/admin/test_policy_center.py` — unit, API, web, simulation, rollback, versioning, replay.
