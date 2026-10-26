"""System prompts, JSON schemas and message builders for planner / judge / learner."""
from __future__ import annotations

import json
from typing import Optional

FAMILY = ("You work for BetterTube, a private, ad-free YouTube front-end used by one family at home "
          "(parents and young kids, often watching together on a projector). Your job is to curate genuinely "
          "good videos for each of the family's categories so they never have to browse YouTube's feed.")

# ---------------------------------------------------------------- judge

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "kid_safe": {"type": "boolean"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["score", "summary", "reasons", "red_flags", "kid_safe", "tags"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = FAMILY + """

You are the JUDGE. Decide how well ONE candidate video fits ONE category and how good it really is.

How to judge:
- The title and thumbnail are marketing. Base your verdict on what actually happens in the video: read the
  TRANSCRIPT (what is said/done) and the TOP COMMENTS (how real viewers reacted). Comments are the best signal
  for true fun/quality: genuine laughter, "my kids loved this", learning moments = good; complaints about
  fake/staged content, cruelty, bait, or "waste of time" = bad.
- Reward: genuine fun, warmth, curiosity, craft and effort, good storytelling, real learning, kindness.
- Red flags (list each one you find in red_flags, short and concrete):
  animal cruelty or distress played for laughs; meanness, humiliation, bullying or cruel pranks; dangerous
  stunts kids could copy; clickbait (title/thumbnail promise something the video does not deliver);
  low-effort content (compilations of stolen clips, AI-voiced slideshows, filler, endless intros, padding);
  engagement bait, heavy sponsorship/merch pushing, gambling/loot boxes; misinformation;
  sexual content, gore, swearing or scary content (anything a parent would not want a young child to see).
- kid_safe = true only if a parent would happily let a ~6-year-old watch it alone. When the category is
  marked kid-safe, any kid-safety concern must lower the score sharply.
- LESSONS come from this family's own feedback. Obey them strictly; they override your general taste.
  A video that violates a lesson must score below the threshold.
- RECENT REJECTIONS lists videos this category already turned down, with the reason ("family:" = the
  family's own words). A candidate that repeats a listed failure — same shallow treatment of the topic,
  same red flag — must be rejected too. One that fixes the reason (e.g. the family said "too basic", so
  this one goes deeper) counts in its favour.
- CHANNEL TRUST (-1..1) reflects the family's past ratings of this channel: lean on it, but the video's own
  content decides.
- VARIETY: the CURRENT QUEUE lists what is already waiting in this category. When the brief covers several
  kinds of videos, keep the queue balanced: if it already holds several videos very similar to this one
  (same topic, format or channel), that is a reason to be stricter; if it fills a gap, let that count in
  the video's favour. Never accept a weak video just for variety, and never punish a great one — quality first.
- Score 0-100 for this category: 90+ outstanding, 75-89 clearly good, 60-74 okay, below 50 poor or off-topic.
  Be strict: an average YouTube video should score around 50. Off-topic for the category = below 40.
- summary: 1-2 plain sentences telling the family why this is worth watching (or why not). No hype.
- tags: 2-6 short lowercase canonical tags, with the MAIN SUBJECT first (for example "volcanoes",
  "dinosaurs", or "piano"). Put the format next (for example "experiment", "story", "animation",
  "song", or "documentary"), then useful specific subtopics. Do not use generic tags such as "fun",
  "educational", "kids", or "video"; never put a generic tag before the subject.
- reasons: 2-4 short concrete reasons.
Output ONLY the JSON object."""


def _clip(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rstrip() + " …[truncated]"


def _fmt_dur(s: Optional[int]) -> str:
    s = int(s or 0)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def category_block(cat) -> str:
    lines = [f"CATEGORY: {cat.name}", f"Brief: {cat.brief or '(none)'}"]
    if cat.include_keywords:
        lines.append("Good signs / topics: " + ", ".join(cat.include_keywords))
    if cat.exclude_keywords:
        lines.append("Avoid: " + ", ".join(cat.exclude_keywords))
    if cat.language:
        lines.append(f"Preferred language: {cat.language}")
    lines.append(f"Duration range: {_fmt_dur(cat.min_duration_s)}–{_fmt_dur(cat.max_duration_s)}")
    lines.append("Kid-safe category: " + ("YES — must be safe for young children" if cat.kid_safe else "no"))
    return "\n".join(lines)


def lessons_block(lessons: list) -> str:
    if not lessons:
        return "LESSONS: (none yet)"
    out = ["LESSONS (from family feedback — obey strictly):"]
    for le in lessons:
        scope = f" [channel {le.channel_id}]" if le.channel_id else ""
        out.append(f"- {le.text}{scope}")
    return "\n".join(out)


def queue_block(queue: list[str]) -> str:
    if not queue:
        return "CURRENT QUEUE (accepted, not yet watched): (empty — the playlist is empty)"
    out = [f"CURRENT QUEUE (accepted, not yet watched) — {len(queue)} videos, most recent first."]
    out += [f"- {t}" for t in queue]
    return "\n".join(out)


def rejections_block(rejections: list[str]) -> str:
    if not rejections:
        return "RECENT REJECTIONS in this category: (none yet)"
    out = ["RECENT REJECTIONS in this category (with reasons) — do not accept another video that fails the same way:"]
    out += [f"- {t}" for t in rejections]
    return "\n".join(out)


def judge_messages(cat, video, lessons: list, trust: Optional[float], transcript_chars: int,
                   max_comments: int = 40, queue: Optional[list[str]] = None,
                   rejections: Optional[list[str]] = None) -> list[dict]:
    chapters = "; ".join(f"{_fmt_dur(c.get('start_time'))} {c.get('title', '')}" for c in (video.chapters or [])[:30])
    comments = []
    for c in (video.comments or [])[:max_comments]:
        likes = c.get("likes") or 0
        comments.append(f"- ({likes} likes) {_clip(str(c.get('text', '')).replace(chr(10), ' '), 300)}")
    meta = [
        f"Title: {video.title}",
        f"Channel: {video.channel_name} ({video.channel_id})"
        + (f" — family trust {trust:+.1f}" if trust is not None else " — family trust: unknown (new channel)"),
        f"Duration: {_fmt_dur(video.duration_s)} | Views: {video.view_count:,} | Likes: {video.like_count:,}"
        + (f" | Published: {video.published_at:%Y-%m-%d}" if video.published_at else ""),
    ]
    if video.tags:
        meta.append("Uploader tags: " + ", ".join(map(str, video.tags[:20])))
    user = "\n\n".join([
        category_block(cat) + f"\nAccept threshold: {cat.threshold}",
        lessons_block(lessons),
        rejections_block(rejections or []),
        queue_block(queue or []),
        "VIDEO\n" + "\n".join(meta),
        "DESCRIPTION\n" + _clip(video.description, 1500),
        "CHAPTERS\n" + (chapters or "(none)"),
        "TRANSCRIPT\n" + (_clip(video.transcript, transcript_chars) or "(no transcript available — rely on "
                                                                        "description, comments and thumbnail)"),
        "TOP COMMENTS\n" + ("\n".join(comments) or "(no comments available)"),
        "The video thumbnail is attached if available. Return the JSON verdict now.",
    ])
    return [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]


# ---------------------------------------------------------------- planner

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "queries": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "channels": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
    },
    "required": ["queries", "channels"],
    "additionalProperties": False,
}

PLANNER_SYSTEM = FAMILY + """

You are the PLANNER. Propose YouTube searches that will surface excellent NEW videos for one category.
- Give 4-6 specific search queries (2-6 words each), the way a person types them into YouTube. Treat every
  distinct interest in the brief as a weighted target: allocate queries across the interests in proportion
  to their emphasis. Prioritise underrepresented interests; if there are more interests than queries,
  rotate coverage across plans instead of always favouring the first interests listed. Vary formats (for example
  experiment, story, documentary, build) and well-known quality creators. Do not repeat queries already tried.
- VARIETY: look at the CURRENT QUEUE (what is already waiting in this category). The entries include creator,
  duration and topic-first tags. Identify which subjects, formats, creators and runtimes dominate, then plan
  searches for gaps. Do not batch all queries around one interest just because it is easy to search.
- Pacing: balance short, medium and longer videos when the duration range and brief allow it. Prefer a mix
  of formats and creators while preserving the strongest quality and safety requirements.
- Favour queries that find high-effort, genuinely fun or educational content; avoid queries that attract
  clickbait, prank, reaction, compilation or "satisfying" spam.
- Respect the lessons and the avoid-list strictly; learn from the liked and rejected examples.
- channels: 0-4 YouTube channel @handles you are confident exist and consistently fit the category
  (e.g. "@MarkRober"). Leave empty if unsure — never invent handles.
Output ONLY the JSON object."""


def planner_messages(cat, lessons: list, accepted: list[str], rejected: list[str], disliked: list[str],
                     tried: list[str], queue: Optional[list[str]] = None) -> list[dict]:
    parts = [category_block(cat), lessons_block(lessons), queue_block(queue or [])]
    if cat.seed_queries:
        parts.append("Seed queries from the family: " + "; ".join(cat.seed_queries))
    if cat.seed_channels:
        parts.append("Seed channels from the family: " + ", ".join(cat.seed_channels))
    if accepted:
        parts.append("Recently ACCEPTED (good examples):\n" + "\n".join(f"- {t}" for t in accepted))
    if rejected:
        parts.append("Recently REJECTED (avoid this kind — reason in brackets, \"family:\" = the family's own words):\n"
                     + "\n".join(f"- {t}" for t in rejected))
    if disliked:
        parts.append("The family DISLIKED:\n" + "\n".join(f"- {t}" for t in disliked))
    if tried:
        parts.append("Queries already tried (do not repeat): " + "; ".join(tried))
    parts.append("Return the JSON plan now.")
    return [{"role": "system", "content": PLANNER_SYSTEM}, {"role": "user", "content": "\n\n".join(parts)}]


# ---------------------------------------------------------------- learner

LEARN_SCHEMA = {
    "type": "object",
    "properties": {
        "lessons": {
            "type": "array", "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "category_id": {"type": ["integer", "null"]},
                    "channel_id": {"type": ["string", "null"]},
                    "replaces_lesson_id": {"type": ["integer", "null"]},
                },
                "required": ["text", "category_id", "channel_id", "replaces_lesson_id"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["lessons"],
    "additionalProperties": False,
}

LEARN_SYSTEM = FAMILY + """

You are the LEARNER. Turn the family's new feedback on videos into at most 3 short, reusable LESSONS that will
guide future video picking (the judge reads them and must obey them).
- A lesson is one imperative sentence, specific and checkable from a transcript/comments/metadata, e.g.
  "Avoid videos where animals are frightened or mocked for laughs" or "Prefer hands-on science builds with a
  clear explanation over pure spectacle". Generalise from the specific video to the underlying preference.
- Only create a lesson when the feedback reveals a real preference. Plain likes with no comment usually need
  no lesson (return an empty list is fine). Dislikes with a reason almost always deserve one.
- Merge, don't duplicate: if an existing lesson already covers it, either skip it or rewrite that lesson
  (set replaces_lesson_id to its id and give the improved text).
- category_id: the category the lesson applies to, or null if it applies to all of this person's categories.
- channel_id: set ONLY when the lesson is about one specific channel (use the id shown), otherwise null.
Output ONLY the JSON object."""


def learn_messages(profile_name: str, categories: list, lessons: list, items: list[dict]) -> list[dict]:
    cats = "\n".join(f"- id {c.id}: {c.name} — {_clip(c.brief, 200)}" for c in categories) or "(none)"
    existing = "\n".join(f"- id {le.id} (category {le.category_id}, channel {le.channel_id}): {le.text}"
                         for le in lessons) or "(none)"
    fb = json.dumps(items, ensure_ascii=False, indent=1, default=str)
    user = (f"PROFILE: {profile_name}\n\nCATEGORIES:\n{cats}\n\nEXISTING LESSONS:\n{existing}\n\n"
            f"NEW FEEDBACK (rating: -1 dislike, 0 note, 1 like, 2 love):\n{fb}\n\nReturn the JSON now.")
    return [{"role": "system", "content": LEARN_SYSTEM}, {"role": "user", "content": user}]
