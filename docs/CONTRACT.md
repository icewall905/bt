# Build contract & tickets

Shared reference for every agent working on this repo. `docs/PLAN.md` = approved design.
Repo: `git@github.com:icewall905/bt.git` (local `/home/hnyg/git/bt`). App code name: **bt** (BetterTube).
Deploy: `root@10.0.10.73:/root/compose/bt`, port **6645**, public URL `https://bt.tdgs.org` (rproxy 10.0.10.60).

## Changes after plan approval (user requests)
- **Profiles** (family members): switcher top-right, no PIN. Profile owns categories, feedback,
  lessons, subscriptions/blocks, watch history. Frontend sends `X-Profile-Id: <id>` header on every
  API call (stored in localStorage `bt.profile`). Backend falls back to first profile.
- **Pause AI** button always visible (status pill in top bar + Agent page): `POST /api/agent/pause`
  / `/api/agent/resume` (`/api/agent/reset-backoff` separately clears a bot-check backoff). When paused the worker makes **no YouTube and no LLM calls**.
- Build material lives in this repo; commit when ready (no AI attribution trailers in commits).

## Layout / ownership
```
backend/
  requirements.txt            pinned deps (py 3.12)
  bt/config.py                env + DEFAULT_SETTINGS                     [lead, done]
  bt/models.py                SQLModel tables                             [lead, done]
  bt/db.py                    engine, settings, agent state/control, emit(), log_yt_request() [lead, done]
  bt/auth.py                  optional BT_PASSWORD cookie auth            [lead, done]
  bt/main.py                  app, routers, SPA serving                   [lead, done]
  bt/api/core.py              profiles/categories/feeds/channels/feedback/lessons/history/settings [lead, done]
  bt/api/agent.py             agent status/control/SSE/llm-test          [lead, done]
  bt/ytdl.py                  yt-dlp wrapper                              [ticket A]
  bt/feeds.py                 channel RSS                                 [ticket A]
  bt/streams.py               DASH MPD + signed range proxy               [ticket A]
  bt/extras.py                SponsorBlock, RYD, DeArrow clients          [ticket A]
  bt/api/video.py             router: search/video/streams/proxy/thumb/channel [ticket A]
  bt/llm.py                   OpenAI-compatible chat client               [ticket B]
  bt/agent/*.py               worker: __main__, loop, ratelimit, planner, enrich, judge, learn [ticket B]
  tests/                      pytest                                      [A: test_streams/test_ytdl, B: test_agent]
frontend/                     SvelteKit SPA (adapter-static) + PWA        [ticket C]
Dockerfile, compose.yaml, host/  packaging + desktop integration           [lead]
```
Do not edit files owned by another ticket. If you need a change there, describe it in your report.

## Conventions
- DB access: `from bt.db import session` (`with session() as s:`), FastAPI dependency `get_session`.
- Settings: `get_settings()` returns merged dict, keys: `llm`, `throttle`, `agent`, `player`,
  `sponsorblock`, `extras` (see `config.DEFAULT_SETTINGS`).
- Agent visibility: `emit(kind, message, level, category_id=, video_id=, profile_id=, payload=)`;
  current activity: `set_agent_state(state=..., detail=..., ...)`.
- Every outbound YouTube request: `log_yt_request(kind, origin="worker"|"user", ok, detail)`.
- Times are **timezone-aware UTC** (`models.now()`); sqlmodel 0.0.48 rejects naive datetimes. Store ISO strings with offset in JSON (`now().isoformat()`).

## ytdl.py interface (A implements, B consumes) — all **sync**, worker calls them in a thread
```python
class YtError(Exception): ...
class YtBlocked(YtError): ...      # 429, "Sign in to confirm you're not a bot", captcha, HTTP 403 on API
class YtUnavailable(YtError): ...  # private/removed/age-gated without cookies/members-only

def search(query: str, n: int = 15, origin: str = "worker") -> list[dict]     # flat, cheap
def channel_videos(ref: str, n: int = 30, origin: str = "worker") -> tuple[dict, list[dict]]
    # ref = UC id | @handle | URL ; returns (channel{id,name,handle,avatar}, entries)
def video_info(video_id: str, origin: str = "worker") -> dict   # full yt-dlp info, in-memory TTL cache 4h
def upsert_video(s, info_or_entry: dict) -> Video               # map yt-dlp dict -> Video row (no commit)
def transcript(info: dict, max_chars: int, langs: list[str] | None = None) -> str
    # manual subs preferred over auto; json3/vtt -> plain text; "" if none; requests logged
def comments(video_id: str, max_comments: int = 40, origin: str = "worker") -> list[dict]
    # top-sorted, [{author, text, likes}], no replies
```
Entry dict (search/channel): `{id,title,channel_id,channel_name,duration_s,view_count,thumbnail,published_at|None,is_short,is_live}`.
yt-dlp options: PO-token provider plugin `bgutil-ytdlp-pot-provider` with
`extractor_args={"youtubepot-bgutilhttp": {"base_url": [POT_URL]}}`; cookiefile = `COOKIES_PATH` if exists;
quiet, no download. Shorts: duration ≤ 60 s or `/shorts/` url.

## api/video.py endpoints (A)
| method | path | returns |
|---|---|---|
| GET | `/api/search?q=&n=20` | `[video_out]` (origin=user, upserts Video rows) |
| GET | `/api/video/{id}` | `video_out(full)` + `channel{id,name,avatar,subscribed,blocked}` + `dislikes` (RYD, optional) + `dearrow{title,thumb}` (if enabled) + `in_categories:[{category_id,candidate_id,score,summary,reasons}]` for active profile + `history{position_s,finished}` |
| GET | `/api/video/{id}/manifest.mpd` | DASH MPD (all segment URLs → signed `/api/proxy/...`), `?max_height=` |
| GET | `/api/video/{id}/fallback` | 302 → signed proxy URL of best progressive (muxed) format |
| GET | `/api/proxy/{token}` | streaming range proxy to googlevideo (Range passthrough, 206, chunked). token = itsdangerous-signed URL with expiry; never an open proxy |
| GET | `/api/video/{id}/captions` | `[{lang,name,auto,url:"/api/video/{id}/captions/{lang}.vtt"}]` |
| GET | `/api/video/{id}/captions/{lang}.vtt` | WebVTT |
| GET | `/api/video/{id}/sponsorblock` | `[{segment:[start,end],category,actionType,UUID}]` (k-anonymous sha256 prefix API, cached 1h, `[]` on error) |
| GET | `/api/video/{id}/comments?n=40` | `[{author,text,likes}]` |
| GET | `/api/thumb/{id}?q=hq|mq|maxres` | cached image (disk cache under DATA_DIR/thumbs, long cache headers) |
| GET | `/api/channel/{ref}` | `{channel, videos:[video_out]}` |
| GET | `/api/channel/{id}/avatar` | cached avatar image |

`video_out` lives in `api/core.py` (import it). Live streams: return 409 `{"detail":"live not supported"}` from manifest (v1).

## Agent worker (B): `python -m bt.agent`
Loop per docs/PLAN.md "AI curator": plan → discover → enrich → judge → learn. Requirements:
- Reads control each iteration: `paused` (sleep, state=`paused`), `run_now` (skip sleep, clear it), `playing_until`
  (+ throttle.pause_while_playing → state `waiting`), `backoff_reset`.
- `agent.enabled` setting false → idle.
- Rate limiter (`agent/ratelimit.py`): single YT request at a time, jittered delay min..max, per-hour/day caps
  computed from `YtRequest` table (worker origin), circuit breaker on `YtBlocked` with exp backoff
  backoff_min..backoff_max persisted in `agent_state` (`state=backoff`, `until`). Quiet hours.
- During every wait: `set_agent_state(state="sleeping", detail=..., until=iso, category_id=...)` so UI can count down.
- States: `offline | idle | paused | waiting | sleeping | backoff | planning | searching | fetching | transcript | comments | judging | learning | error`.
- Category picking: enabled categories across **all profiles**, weight = priority × deficit (target_queue − accepted unwatched),
  skip if deficit ≤ 0, prefer least-recently worked; process `found`→`enriched`→judged backlog before new searches.
- Planner prompt includes category brief, seed queries/channels, include/exclude keywords, lessons (profile+category scoped,
  active), recent accepted/rejected titles, recent dislike feedback. Output JSON `{queries:[...], channels:[...]}`. Also uses
  subscribed channel RSS (`feeds.channel_feed`) and seed_channels via `channel_videos`.
- Prefilter before enrich: duration range, is_short (if hide_shorts), is_live, exclude keywords in title, blocked channels for the
  profile, already candidate in this category, max_age_days.
- Enrich: `video_info` + `transcript` + `comments`, stored on Video (enriched_at), reused across categories.
- Judge prompt: category brief, lessons, channel trust, metadata, description, chapters, transcript (truncated), top comments,
  thumbnail as image (`image_url` = data URL of `/thumb` bytes) when `llm.vision`. Strict JSON:
  `{score:int 0-100, summary:str (1-2 sentences, why fun/relevant), reasons:[str], red_flags:[str], kid_safe:bool, tags:[str]}`.
  kid_safe category → reject if `kid_safe` false. Accept if score ≥ category.threshold.
- Learn: unprocessed Feedback → LLM distills ≤3 lesson rows (merge/dedupe with existing lessons; may set channel_id), adjust
  ProfileChannel.trust (+0.2 like/love, −0.3 dislike, clamp −1..1; trust ≤ −0.8 ⇒ treated as blocked by prefilter). Mark processed.
  Learning has priority over searching (runs as soon as feedback arrives, no YT calls).
- LLM failures: retry ×2, then leave candidate in `enriched` and back off LLM for 5 min (emit warn). Parse JSON robustly
  (strip ```json fences / <think> blocks, take first {...}).
- Emit an AgentEvent for every meaningful step with human text, e.g. `🔎 Searching "mark rober egg drop" for Kids`,
  `📜 Reading transcript: <title>`, `💬 Reading 40 comments`, `✅ Accepted (82): <title> — <summary>`,
  `❌ Rejected (31): <title> — <red flag>`, `🧠 Learned: "Avoid ..."`, `⏸️ Paused`, `🛑 YouTube bot-check — backing off 1h`.

## Frontend (C)
See ticket C brief (in agent prompt / `frontend/README.md` once written). API above + `api/core.py` + `api/agent.py`.
SSE: `GET /api/agent/stream` events `state` and `agent`.
