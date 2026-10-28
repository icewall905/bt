"""Request sizes only: never persist prompts, credentials or image payloads here."""
from datetime import timedelta
import logging
import math

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
        core = system.split("CORE IDENTITY / KNOWLEDGE / RULES\n", 1)[-1].split("\n\nRECENT CORRECTIONS", 1)[0] if "CORE IDENTITY / KNOWLEDGE / RULES\n" in system else ""
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


def overview(s):
    since = now() - timedelta(hours=24)
    rows = s.exec(select(LlmRequest).where(LlmRequest.created_at >= since)).all()
    good = [r for r in rows if r.ok]
    tasks = {}
    for row in good:
        tasks.setdefault(row.task, []).append(row)
    total = sum(r.input_tokens for r in good)
    return {"requests": len(good), "failed": len(rows) - len(good),
        "average_input_tokens": round(total / len(good)) if good else 0,
        "max_input_tokens": max((r.input_tokens for r in good), default=0),
        "estimated_requests": sum(r.estimated for r in good),
        "cached_tokens": sum(r.cached_tokens for r in good),
        "average_core_chars": round(sum(r.core_chars for r in good) / len(good)) if good else 0,
        "average_correction_chars": round(sum(r.correction_chars for r in good) / len(good)) if good else 0,
        "by_task": [{"task": task, "requests": len(rs), "average_input_tokens": round(sum(r.input_tokens for r in rs) / len(rs))}
                    for task, rs in sorted(tasks.items())], "window_hours": 24}
