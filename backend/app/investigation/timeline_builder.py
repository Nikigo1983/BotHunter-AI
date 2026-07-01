from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.audit_log import AuditLog
from app.models.enums import AnalysisDecision, JoinRequestStatus
from app.models.manual_review import ManualReview


@dataclass(slots=True)
class TimelineEventDTO:
    stage: str
    title: str
    timestamp: datetime | None
    duration_ms: int | None
    result: str | None
    details: dict[str, Any] | None = None


STAGE_TITLES = {
    "join_request_received": "Join Request received",
    "feature_extraction": "Feature Extraction",
    "rule_engine": "Rule Engine",
    "risk_profile": "Risk Profile",
    "ai_prompt": "AI Prompt",
    "openrouter_response": "OpenRouter Response",
    "decision_engine": "Decision Engine",
    "admin_decision": "Admin Decision",
    "telegram_action": "Telegram Action",
}


class TimelineBuilder:
    @staticmethod
    def build(
        *,
        created_at: datetime,
        analysis_created_at: datetime | None,
        explanation: dict[str, Any],
        analysis_decision: AnalysisDecision | None,
        rule_score: float | None,
        join_status: JoinRequestStatus,
        telegram_action: str,
        manual_reviews: list[ManualReview],
        audit_logs: list[AuditLog],
        rule_engine_decision: AnalysisDecision | None,
        ai_status: str | None = None,
    ) -> list[TimelineEventDTO]:
        ai_result = explanation.get("ai_result") or {}
        risk_profile = explanation.get("risk_profile") or {}
        legacy = explanation.get("legacy_explanation")

        if legacy and not explanation.get("triggered_rules"):
            return TimelineBuilder._build_short_path(
                created_at=created_at,
                legacy=legacy,
                join_status=join_status,
                telegram_action=telegram_action,
                manual_reviews=manual_reviews,
                audit_logs=audit_logs,
            )

        analysis_at = analysis_created_at or created_at
        events: list[tuple[str, datetime | None, str | None, dict[str, Any] | None]] = [
            ("join_request_received", created_at, "received", None),
            ("feature_extraction", created_at, "features extracted", None),
            (
                "rule_engine",
                analysis_at,
                f"rule_score={rule_score}" if rule_score is not None else "evaluated",
                {"triggered_rules": explanation.get("triggered_rules", [])},
            ),
            (
                "risk_profile",
                analysis_at,
                risk_profile.get("risk_level") or "built",
                {"summary": risk_profile.get("summary")},
            ),
        ]

        if ai_status and ai_status != "SKIPPED":
            events.extend(
                [
                    ("ai_prompt", analysis_at, "prompt prepared", None),
                    (
                        "openrouter_response",
                        analysis_at,
                        ai_status,
                        {
                            "provider": ai_result.get("provider"),
                            "model": ai_result.get("model"),
                            "decision": ai_result.get("decision"),
                        },
                    ),
                ]
            )
        elif ai_status == "SKIPPED":
            events.append(("ai_prompt", analysis_at, "skipped", None))

        if analysis_decision is not None:
            events.append(
                (
                    "decision_engine",
                    analysis_at,
                    analysis_decision.value,
                    {"source": "final_decision"},
                )
            )

        admin_event = TimelineBuilder._resolve_admin_event(manual_reviews, audit_logs)
        if admin_event is not None:
            events.append(admin_event)

        telegram_event = TimelineBuilder._resolve_telegram_event(
            audit_logs=audit_logs,
            join_status=join_status,
            telegram_action=telegram_action,
            fallback_at=analysis_at,
        )
        if telegram_event is not None:
            events.append(telegram_event)

        return TimelineBuilder._with_durations(events)

    @staticmethod
    def _build_short_path(
        *,
        created_at: datetime,
        legacy: str,
        join_status: JoinRequestStatus,
        telegram_action: str,
        manual_reviews: list[ManualReview],
        audit_logs: list[AuditLog],
    ) -> list[TimelineEventDTO]:
        events: list[tuple[str, datetime | None, str | None, dict[str, Any] | None]] = [
            ("join_request_received", created_at, "received", None),
            ("feature_extraction", created_at, legacy, None),
            ("rule_engine", created_at, "bypassed", None),
            ("decision_engine", created_at, join_status.value, None),
        ]
        admin_event = TimelineBuilder._resolve_admin_event(manual_reviews, audit_logs)
        if admin_event is not None:
            events.append(admin_event)
        telegram_event = TimelineBuilder._resolve_telegram_event(
            audit_logs=audit_logs,
            join_status=join_status,
            telegram_action=telegram_action,
            fallback_at=created_at,
        )
        if telegram_event is not None:
            events.append(telegram_event)
        return TimelineBuilder._with_durations(events)

    @staticmethod
    def _resolve_admin_event(
        manual_reviews: list[ManualReview],
        audit_logs: list[AuditLog],
    ) -> tuple[str, datetime | None, str | None, dict[str, Any] | None] | None:
        if manual_reviews:
            latest = max(manual_reviews, key=lambda item: item.created_at)
            return (
                "admin_decision",
                latest.created_at,
                latest.final_decision.value,
                {"admin_action": latest.admin_action.value},
            )
        admin_actions = {
            log.created_at: log.action
            for log in audit_logs
            if log.action in {"approve", "reject", "whitelist", "blacklist"}
        }
        if not admin_actions:
            return None
        latest_at = max(admin_actions)
        return ("admin_decision", latest_at, admin_actions[latest_at], None)

    @staticmethod
    def _resolve_telegram_event(
        *,
        audit_logs: list[AuditLog],
        join_status: JoinRequestStatus,
        telegram_action: str,
        fallback_at: datetime,
    ) -> tuple[str, datetime | None, str | None, dict[str, Any] | None] | None:
        telegram_logs = [
            log
            for log in audit_logs
            if log.action in {"approve", "reject", "approve_error", "reject_error"}
        ]
        timestamp = telegram_logs[-1].created_at if telegram_logs else fallback_at
        result = telegram_action if join_status != JoinRequestStatus.PENDING else "pending"
        return ("telegram_action", timestamp, result, None)

    @staticmethod
    def _with_durations(
        events: list[tuple[str, datetime | None, str | None, dict[str, Any] | None]],
    ) -> list[TimelineEventDTO]:
        timeline: list[TimelineEventDTO] = []
        previous_ts: datetime | None = None
        for stage, timestamp, result, details in events:
            duration_ms = None
            if timestamp is not None and previous_ts is not None:
                duration_ms = max(0, int((timestamp - previous_ts).total_seconds() * 1000))
            if timestamp is not None:
                previous_ts = timestamp
            timeline.append(
                TimelineEventDTO(
                    stage=stage,
                    title=STAGE_TITLES.get(stage, stage),
                    timestamp=timestamp,
                    duration_ms=duration_ms,
                    result=result,
                    details=details,
                )
            )
        return timeline
