"""Request sizes only: never persist prompts, credentials or image payloads here."""
from datetime import timedelta
import logging
import math
import re

from sqlmodel import delete, func, select

from .db import session
from .models import LlmRequest, now

log = logging.getLogger("bt.llm")


def record(body, task, response=None):
    try:
        usage = {}
        if response is not None:
            try:
                usage = response.json().get("usage") or {}
            except (ValueError, AttributeError):
                pass
        texts = []
        for message in body["messages"]:
            content = message.get("content", "")
            texts.append(content if isinstance(content, str) else "\n".join(
                part.get("text", "") for part in content if isinstance(part, dict)))
        chars = sum(map(len, texts))
        system = texts[0] if texts else ""
        core = re.split(r"\n\n(?:MEMORY PRIORITY|RECENT CORRECTIONS|TASK INSTRUCTIONS)",
                        system.split("CORE IDENTITY / KNOWLEDGE / RULES\n", 1)[-1], maxsplit=1)[0] if "CORE IDENTITY / KNOWLEDGE / RULES\n" in system else ""
        corrections = system.split("RECENT CORRECTIONS\n", 1)[-1].split("\n\nTASK INSTRUCTIONS", 1)[0] if "RECENT CORRECTIONS\n" in system else ""
        tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        estimated = not isinstance(tokens, int) or tokens < 0
        cached = (usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
        with session() as s:
            s.add(LlmRequest(task=task, model=body["model"], input_tokens=math.ceil(chars / 4) if estimated else tokens,
                cached_tokens=max(0, cached) if isinstance(cached, int) else 0, estimated=estimated,
                input_chars=chars, core_chars=len(core), correction_chars=len(corrections),
                ok=response is not None and response.status_code < 400))
            s.exec(delete(LlmRequest).where(LlmRequest.created_at < now() - timedelta(days=30)))
            s.commit()
    except Exception:
        log.warning("Could not record LLM request sizes", exc_info=True)


def _summary(rows):
    values = sorted(r.input_tokens for r in rows)
    total = sum(values)
    measured = [r for r in rows if not r.estimated]
    measured_total = sum(r.input_tokens for r in measured)
    cache = sum(min(r.input_tokens, max(0, r.cached_tokens)) for r in measured)
    return {"requests": len(rows), "total_input_tokens": total,
            "average_input_tokens": round(total / len(rows)) if rows else 0,
            "median_input_tokens": round((values[(len(values) - 1) // 2] + values[len(values) // 2]) / 2) if values else 0,
            "p95_input_tokens": values[max(0, math.ceil(len(values) * 0.95) - 1)] if values else 0,
            "max_input_tokens": max(values, default=0),
            "cache_hit_percent": round(cache / measured_total * 100, 1) if measured_total else None}


def overview(s):
    instant = now()
    since = instant - timedelta(hours=24)
    rows = s.exec(select(LlmRequest).where(LlmRequest.created_at >= since)).all()
    good = [r for r in rows if r.ok]
    tasks, models = {}, {}
    for row in good:
        tasks.setdefault(row.task, []).append(row)
        models.setdefault(row.model, []).append(row)
    start = since.replace(minute=0, second=0, microsecond=0)
    hours = { (start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00:00Z"): [] for i in range(25) }
    for row in good:
        key = row.created_at.strftime("%Y-%m-%dT%H:00:00Z")
        if key in hours:
            hours[key].append(row)
    bins = [("Under 4k", 0, 4000), ("4k–8k", 4000, 8000), ("8k–16k", 8000, 16000),
            ("16k–32k", 16000, 32000), ("32k–64k", 32000, 64000), ("64k+", 64000, float("inf"))]
    from .agent.knowledge import describe
    from .agent.memory import active, fingerprint, latest, sources_valid
    from .db import get_settings
    from .models import LessonEvidenceState, LessonRevision, Profile
    profiles = []
    strengths = {"explicit": 0, "supported pattern": 0, "tentative inference": 0, "unreviewed inference": 0}
    for profile in s.exec(select(Profile).order_by(Profile.id)).all():
        lessons = active(s, profile.id)
        core = latest(s, profile.id)
        valid = bool(core and sources_valid(core, {str(le.id): fingerprint(le) for le in lessons}))
        reviewed = set(s.exec(select(LessonEvidenceState.lesson_id).where(
            LessonEvidenceState.profile_id == profile.id, LessonEvidenceState.updated_at > core.created_at)).all()) if valid else set()
        corrections = [le for le in lessons if not valid or str(le.id) not in core.sources or le.id in reviewed]
        for lesson in lessons:
            strengths[describe(s, lesson)["kind"]] += 1
        profiles.append({"profile_id": profile.id, "profile": profile.name, "core_valid": valid,
            "core_tokens_estimate": math.ceil(len(core.text) / 4) if valid else 0,
            "stored_core_tokens_estimate": math.ceil(len(core.text) / 4) if core else 0,
            "core_budget_tokens": core.budget_tokens if core else None,
            "raw_rule_tokens_estimate": math.ceil(sum(len(le.text) for le in lessons) / 4),
            "correction_tokens_estimate": math.ceil(sum(len(le.text) for le in corrections) / 4),
            "active_rules": len(lessons), "corrections": len(corrections)})
    return {**_summary(good), "failed": len(rows) - len(good),
        "estimated_requests": sum(r.estimated for r in good), "measured_requests": sum(not r.estimated for r in good),
        "cached_tokens": sum(min(r.input_tokens, max(0, r.cached_tokens)) for r in good),
        "average_core_chars": round(sum(r.core_chars for r in good) / len(good)) if good else 0,
        "average_correction_chars": round(sum(r.correction_chars for r in good) / len(good)) if good else 0,
        "average_other_chars": round(sum(max(0, r.input_chars - r.core_chars - r.correction_chars) for r in good) / len(good)) if good else 0,
        "by_task": [{"task": task, **_summary(rs)} for task, rs in sorted(tasks.items())],
        "by_model": [{"model": model, **_summary(rs)} for model, rs in sorted(models.items())],
        "hourly": [{"hour": hour, **_summary(rs)} for hour, rs in hours.items()],
        "distribution": [{"label": label, "requests": sum(lower <= r.input_tokens < upper for r in good)}
                         for label, lower, upper in bins],
        "memory_profiles": profiles, "rule_strengths": strengths,
        "revisions_24h": s.exec(select(func.count()).select_from(LessonRevision).where(LessonRevision.created_at >= since)).one(),
        "configured_core_budget_tokens": get_settings(s)["memory"]["max_core_tokens"],
        "window_hours": 24}
