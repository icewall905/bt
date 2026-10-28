"""Learn from unprocessed feedback: distil lessons (LLM) + adjust channel trust. No YouTube calls."""
from __future__ import annotations

from collections import defaultdict

from sqlmodel import col, select

from ..db import session
from ..models import Candidate, Category, Feedback, Lesson, Profile, ProfileChannel, Video, now
from . import prompts
from .runtime import Interrupt, Runtime

BATCH = 8
TRUST_DELTA = {2: 0.2, 1: 0.2, -1: -0.3}
APPROVED_REJECTION = "Approved rejection"


def _norm(t: str) -> str:
    return " ".join("".join(ch for ch in t.lower() if ch.isalnum() or ch.isspace()).split())


def pending_count() -> int:
    with session() as s:
        return len(s.exec(select(Feedback.id).where(Feedback.processed == False)).all())  # noqa: E712


def _items(s, fbs: list[Feedback]) -> tuple[list[dict], set[str]]:
    items, channels = [], set()
    for f in fbs:
        v = s.get(Video, f.video_id)
        cat = s.get(Category, f.category_id) if f.category_id else None
        cand = (s.exec(select(Candidate).where(Candidate.category_id == f.category_id,
                                               Candidate.video_id == f.video_id)).first()
                if f.category_id else None)
        if v and v.channel_id:
            channels.add(v.channel_id)
        items.append({
            "feedback_id": f.id, "rating": f.rating, "chips": f.chips, "text": f.text,
            "category_id": f.category_id, "category": cat.name if cat else None,
            "video_title": v.title if v else f.video_id,
            "channel": f"{v.channel_name} (id {v.channel_id})" if v and v.channel_id else None,
            "ai_summary_when_picked": cand.summary if cand else None,
            "ai_score_when_picked": cand.score if cand else None,
            "ai_reasons_when_picked": cand.reasons if cand else None,
            "ai_red_flags_when_picked": cand.red_flags if cand else None,
            "ai_tags": cand.tags if cand else None,
            "description_excerpt": (v.description or "")[:300] if v else None,
        })
    return items, channels


def _adjust_trust(s, profile_id: int, fbs: list[Feedback]) -> list[dict]:
    changes = []
    for f in fbs:
        # This rating is a correction to the AI's rejection, not approval of the channel.
        if f.rating == 1 and APPROVED_REJECTION in (f.chips or []):
            continue
        delta = TRUST_DELTA.get(f.rating)
        v = s.get(Video, f.video_id)
        if not delta or not v or not v.channel_id:
            continue
        pc = s.exec(select(ProfileChannel).where(ProfileChannel.profile_id == profile_id,
                                                 ProfileChannel.channel_id == v.channel_id)).first()
        pc = pc or ProfileChannel(profile_id=profile_id, channel_id=v.channel_id)
        old = pc.trust or 0.0
        pc.trust = round(max(-1.0, min(1.0, old + delta)), 3)
        s.add(pc)
        changes.append({"channel_id": v.channel_id, "channel": v.channel_name, "from": old, "to": pc.trust})
    return changes


def process(rt: Runtime) -> int:
    """Process up to one batch of feedback per profile. Returns number of feedback rows processed."""
    with session() as s:
        fbs = s.exec(select(Feedback).where(Feedback.processed == False)  # noqa: E712
                     .order_by(col(Feedback.created_at)).limit(50)).all()
    if not fbs:
        return 0
    by_profile: dict[int, list[Feedback]] = defaultdict(list)
    for f in fbs:
        if len(by_profile[f.profile_id]) < BATCH:
            by_profile[f.profile_id].append(f)
    done = 0
    for pid, batch in by_profile.items():
        rt.check()
        if not rt.llm_ok():
            break
        done += _process_profile(rt, pid, batch)
    return done


def _process_profile(rt: Runtime, pid: int, batch: list[Feedback]) -> int:
    with session() as s:
        prof = s.get(Profile, pid)
        cats = list(s.exec(select(Category).where(Category.profile_id == pid)).all())
        lessons = list(s.exec(select(Lesson).where(Lesson.profile_id == pid, Lesson.active == True)).all())  # noqa: E712
        from .memory import select_memory
        core, lessons = select_memory(s, pid, lessons)
        items, channels = _items(s, batch)
    meaningful = [it for it in items if it["rating"] != 0 or it["chips"] or (it["text"] or "").strip()]
    out_lessons: list[dict] = []
    if meaningful:
        rt.state("learning", f"Learning from {len(batch)} feedback item(s)", None, profile_id=pid)
        rt.event("learn", f"🧠 Learning from {len(batch)} new feedback item(s) ({prof.name if prof else pid})",
                 "info", profile_id=pid, payload={"feedback_ids": [f.id for f in batch]})
        msgs = prompts.learn_messages(prof.name if prof else str(pid), cats, lessons, meaningful, core=core)
        try:
            out = rt.llm.chat_json(msgs, json_schema=prompts.LEARN_SCHEMA, max_tokens=2500, schema_name="lessons",
                                   abort=rt.check)
        except Interrupt:
            raise
        except Exception as e:  # noqa: BLE001
            rt.llm_failed("learning from feedback", e, profile_id=pid)
            return 0
        out_lessons = [x for x in (out.get("lessons") or []) if isinstance(x, dict)][:3]

    cat_ids = {c.id for c in cats}
    fb_ids = [f.id for f in batch]
    learned, trust = [], []
    with session() as s:
        existing = {le.id: le for le in s.exec(select(Lesson).where(Lesson.profile_id == pid)).all()}
        norm_existing = {_norm(le.text): le for le in existing.values() if le.active}
        for x in out_lessons:
            text = str(x.get("text") or "").strip()[:500]
            if not text:
                continue
            cid = x.get("category_id")
            cid = int(cid) if isinstance(cid, (int, float, str)) and str(cid).isdigit() and int(cid) in cat_ids else None
            ch = x.get("channel_id")
            ch = ch if isinstance(ch, str) and ch in channels else None
            rid = x.get("replaces_lesson_id")
            target = existing.get(int(rid)) if isinstance(rid, (int, float)) or (isinstance(rid, str) and rid.isdigit()) else None
            dup = norm_existing.get(_norm(text))
            if target is None and dup is not None:
                target = dup
            if target is not None:
                changed = target.text != text
                target.text, target.active, target.updated_at = text, True, now()
                target.category_id = cid if cid is not None else target.category_id
                target.channel_id = ch or target.channel_id
                target.source_feedback_ids = sorted(set((target.source_feedback_ids or []) + fb_ids))
                target.weight = round(min(3.0, (target.weight or 1.0) + 0.25), 2)
                s.add(target)
                learned.append((target, "updated" if changed else "reinforced"))
            else:
                le = Lesson(profile_id=pid, category_id=cid, channel_id=ch, text=text, source_feedback_ids=fb_ids)
                s.add(le)
                norm_existing[_norm(text)] = le
                learned.append((le, "new"))
        trust = _adjust_trust(s, pid, batch)
        for f in batch:
            row = s.get(Feedback, f.id)
            row.processed = True
            s.add(row)
        s.commit()
    for le, how in learned:
        rt.event("learn", f'🧠 Learned{"" if how == "new" else f" ({how})"}: "{le.text}"', "success",
                 profile_id=pid, category_id=le.category_id,
                 payload={"lesson_id": le.id, "how": how, "channel_id": le.channel_id})
    for t in trust:
        rt.event("learn", f"📈 Channel trust {t['channel'] or t['channel_id']}: {t['from']:+.1f} → {t['to']:+.1f}",
                 "info", profile_id=pid, payload=t)
    if meaningful and not learned:
        rt.event("learn", "🧠 Feedback noted — no new lesson needed", "debug", profile_id=pid)
    return len(batch)
