# BetterTube (bt) — self-hosted YouTube wrapper with AI curator

## Context
Want: ad-free YouTube front-end on projector host, PWA at `https://bt.tdgs.org` (rproxy 10.0.10.60 → `http://10.0.10.73:6645`), remote-control navigable, plus background AI agent (local LLM `http://10.0.10.23:8080/v1`, model `currentmodel`, 262k ctx, vision) that slowly finds videos per user-defined category, using transcript + top comments + feedback memory. Greenfield. Deploy to `root@10.0.10.73:/root/compose/bt` (dir absent; port 6645 free).

Host facts (inspected):
- Debian 13, 8 cores, 31 GB, RTX 3060, Docker 29 / Compose v5.
- Desktop: user `console`, KDE kwin_x11, Chromium + Firefox present, xbindkeys, xdotool.
- Remote: "HAOBO USB Composite Device" via input-remapper; buttons 1–5 → Ctrl+Shift+U/I/P/L/O (mode scripts in `/home/console/bin/*-mode`), button 6 → Ctrl+Shift+Y (**unbound → use for bt-mode**); OK→Enter, play→Space; arrows/back native keys.
- Existing pattern: `/home/console/bin/vacuumtube-mode` + `mode-common.sh` (1080p60, HDMI sink, kill competitors, fullscreen via xdotool/wmctrl).
- searxng, redis, postgres stacks exist but keep `bt` self-contained.

Decisions (user): **user profiles** (family members, switcher top-right, no PIN) each owning categories, feedback, lessons, subscriptions, history; manual search; local channel subscriptions; optional cookies.txt; add desktop `bt-mode`.

## Architecture

```
compose/bt
├─ bt-api      FastAPI (Python 3.12) + yt-dlp lib + SQLite(WAL)  :6645 (serves SPA too)
├─ bt-worker   same image, `python -m bt.agent` — curator loop + scheduler
├─ pot         bgutil-ytdlp-pot-provider (PO tokens, keeps yt-dlp working)
└─ volumes: ./data (sqlite, thumbs cache, cookies.txt, logs)
```
Single image, two commands. No Redis: SQLite job table + SSE event bus via DB polling/`LISTEN`-like in-proc queue in api; worker writes `agent_events` rows, api streams them.

### Playback (ad-free by construction)
- Never embed youtube.com player → no ads at all.
- `GET /api/video/{id}/streams`: yt-dlp extract (with PO token, cookies if set), cache 4h.
- Backend generates DASH MPD from adaptive formats; **all googlevideo bytes proxied** via `/api/proxy/…` (range requests, streaming httpx) — avoids IP-locked URLs/CORS, client never talks to Google.
- Client player: **Shaka Player** (MSE), H.264/VP9 + AAC/Opus up to 1080p60 (CPU decode ok per vacuumtube note), quality setting, captions (WebVTT from yt-dlp subs).
- SponsorBlock: server fetches `sponsor.ajay.app/api/skipSegments/{sha256prefix}` (privacy hash API), cached; client auto-skips / shows "skip" toast / ignores per category (sponsor, selfpromo, interaction, intro, outro, preview, filler, music_offtopic) per settings; segments drawn on seek bar.
- Also: DeArrow (optional: crowd titles/thumbs), Return YouTube Dislike counts, chapter markers, resume position, playback speed, autoplay next-in-category, hide Shorts toggle, min/max duration filter, blocked channels/keywords.

### Data model (SQLite, SQLModel + Alembic)
- `settings` (kv JSON): LLM base_url/model/api_key, throttle, sponsorblock prefs, player prefs, theme.
- `category`: name, icon/color, description (free-text brief for AI), seed_queries[], seed_channels[], include/exclude keywords, duration range, language, max_age_days, target_queue_size, enabled, priority.
- `channel` (subscriptions + seen): id, name, avatar, subscribed bool, trust score per category, blocked.
- `video`: id, title, channel, duration, published, thumbs, view/like counts, transcript (text, trimmed), top_comments JSON, description, fetched_at.
- `candidate`: video×category, status (found→enriched→judged→accepted/rejected), score, ai_summary, ai_reasons, ai_tags.
- `feedback`: video, category, rating (👍/👎/⭐), free text ("mean to the cat"), created; **`lesson`** rows distilled by LLM (rule text, scope: category/channel/global, weight, source feedback ids, active).
- `watch_history`, `playback_position`, `agent_job`, `agent_event` (timestamp, level, kind, message, payload) for UI.

### AI curator (bt-worker)
Loop, one job at a time, global token-bucket rate limiter:
1. **Plan** (per category, round-robin by priority × queue deficit): LLM gets category brief + active lessons + recent accepts/rejects → returns 3–5 search queries / channels to mine. Plus deterministic sources: subscribed-channel RSS (`/feeds/videos.xml?channel_id=`), related videos of top-rated items.
2. **Discover**: yt-dlp `ytsearchN:` / channel tab (flat, cheap). Dedupe vs seen/rejected/blocked; prefilter duration, age, keywords, shorts.
3. **Enrich** (expensive, throttled hardest): metadata, transcript (yt-dlp auto/manual subs → plain text, cap ~12k tokens; chunk-summarize if longer), top ~40 comments (yt-dlp `getcomments`, `max_comments=40,all,0,0`, sort top), thumbnail (sent to vision model as image).
4. **Judge**: structured JSON (`response_format`/json schema, fallback regex parse): `{score 0-100, fit_reasons, red_flags, kid_safe, summary, tags}`. Prompt contains category brief, lessons, channel trust, comment sentiment. Accept if ≥ threshold (per-category setting).
5. **Learn**: on new feedback, LLM distills into lessons (e.g. "Avoid videos where comments mention animal mistreatment; down-weight channel X"); dedupe/merge lessons; user can view/edit/delete lessons. Channel trust auto-adjusted by ratings.

Throttling/anti-block (defaults, all configurable):
- Max 1 YouTube request in flight; jittered delay 20–60 s between YouTube calls; ≤ 120 YT requests/hour; daily cap.
- Exponential backoff + circuit breaker on 429/"sign in to confirm"/bot-check → pause 1–6 h, shown red in UI.
- Quiet hours option; pause while user is actively playing (avoid competing for IP) — toggle.
- LLM: concurrency 1, timeout, retry; if LLM down → keep discovering/enriching, judge later.
- Queue targets: stop working a category when it holds N fresh unwatched accepted videos.

Agent visibility: worker emits events → `/api/agent/stream` (SSE). UI: persistent status pill (idle / searching "Mark Rober science" / reading transcript / reading comments / judging / sleeping 42s / backoff until 14:10) with animated icon + countdown; Agent page with live log, per-category queue gauges, request budget meters, pause/resume/“run now”, per-candidate reasoning ("why was this picked/rejected").

### API (FastAPI)
`/api/categories` CRUD · `/api/feed?category=` · `/api/search?q=` · `/api/video/{id}` (+streams, sponsorblock, comments, related) · `/api/proxy/*` · `/api/channels` (subscribe/block) · `/api/feedback` · `/api/lessons` CRUD · `/api/agent/{status,stream,pause,resume,run}` · `/api/settings` (+ LLM "test connection") · `/api/cookies` upload. Optional single shared password (settings) since exposed via rproxy; default off on LAN? → **default: simple passphrase login, cookie session** (bt.tdgs.org is public DNS).

### Frontend (SvelteKit static adapter, TypeScript, built into image)
- Dark, cinematic 10-foot UI (works on phone/desktop too): Inter/“Geist” font, large rounded cards, glassy top bar, accent per category color, smooth focus scaling.
- Screens: **Home** (row per category, "Continue watching", "New from subscriptions"), **Category** (grid + AI summaries + "why picked"), **Player** (fullscreen, overlay controls, SponsorBlock bar, chapters, quick feedback 👍/👎/note), **Search** (on-screen keyboard grid), **Subscriptions**, **Agent** (live activity), **Settings** (categories editor, lessons memory, player/SponsorBlock, LLM, throttle, cookies).
- Feedback: after video end / on 👎 → dialog with quick chips ("boring", "mean", "too long", "clickbait", "too hard for kids") + free text (typed on phone or OSK).
- **Spatial navigation**: custom focus engine (or `@noriginmedia/norigin-spatial-navigation`-style): arrow keys move focus geometrically, Enter=select, Backspace/Escape/BrowserBack=back, Space/MediaPlayPause=play/pause, MediaTrackNext/Prev, `?` overlay. Every view has a defined initial focus; focus ring huge & visible; scroll focused into view. Mouse/touch still work. Keymap configurable in settings + "key test" page.
- **PWA**: manifest (standalone, landscape-friendly, icons, theme), service worker (Workbox: precache shell, cache thumbnails, never cache video proxy), installable on phone/desktop.

### Desktop integration (host, outside compose)
- `/home/console/bin/bt-mode` cloned from `vacuumtube-mode`: same competitor kills (+ `pkill -f bt-app`), 1080p60, HDMI sinks, then `chromium --app=https://bt.tdgs.org --kiosk --class=bt-app --user-data-dir=~/.config/bt-app --autoplay-policy=no-user-gesture-required`; xdotool focus/fullscreen.
- Add competitor kill of `bt-app` to other `*-mode` scripts.
- `~/.xbindkeysrc`: `"/home/console/bin/bt-mode"  Control+Shift+y` (remote button 6, already mapped by input-remapper); reload xbindkeys.
- Backups (`.bak.<date>`) of every edited host file.

## Repo layout (local scratch → rsync to host)
```
bt/
├─ compose.yaml  .env.example  Dockerfile (multi-stage: node build → python slim + ffmpeg)
├─ backend/bt/ {main.py, db.py, models.py, ytdl.py, streams.py(dash mpd+proxy), sponsorblock.py,
│               feeds.py, llm.py, agent/{loop.py, planner.py, enrich.py, judge.py, learn.py, ratelimit.py, events.py},
│               api/*.py}
├─ backend/tests/
├─ frontend/src/ {lib/nav (spatial focus), lib/player (shaka+sponsorblock), lib/api, routes/*}
└─ host/ {bt-mode, xbindkeys.snippet, install-desktop.sh}
```
Pinned: yt-dlp nightly-ish pinned version + weekly `pip install -U yt-dlp` option on container restart (YouTube breakage is the #1 risk).

## Tickets (Sol leads; Luna/Terra models not available in this harness → Claude subagents implement/review, lead integrates)
1. Backend core: models, settings, categories/channels/feedback/lessons CRUD, auth, SSE bus. 
2. YouTube layer: yt-dlp wrapper + PO-token sidecar, search, metadata, transcript, comments, RSS feeds, rate limiter/circuit breaker.
3. Streaming: DASH MPD generation + range proxy + SponsorBlock/RYD/DeArrow clients.
4. Agent worker: plan/discover/enrich/judge/learn loop against OpenAI-compatible LLM, events.
5. Frontend shell: SvelteKit, design system, spatial nav engine, PWA.
6. Frontend screens: home/category/player(Shaka+SB)/search+OSK/subs/agent/settings/feedback.
7. Packaging & deploy: Dockerfile, compose, rsync to `/root/compose/bt`, `docker compose up -d`.
8. Host desktop: bt-mode script + xbindkeys binding (after stack verified).
Order: 1 → (2,3,5 parallel) → (4,6) → 7 → 8. Each ticket reviewed before integration.

## Verification
- `pytest` backend: MPD generation, rate limiter/backoff, judge JSON parsing, lesson distillation (LLM mocked) + one live smoke against 10.0.10.23.
- Frontend: `svelte-check`, Playwright: keyboard-only navigation through every screen (arrows/Enter/Backspace), PWA installability (Lighthouse manifest/SW).
- On host: `docker compose ps` healthy; `curl :6645/api/health`; play a known video with sponsor segments → skips occur, no ad requests (network log shows only own origin).
- Agent: create "Videos with kids" + "Grownups" categories, watch live status; confirm throttle (≤ configured req/h in logs), candidates carry transcript+comments, feedback "mean to the cat" produces a lesson and affects next judgments.
- Via rproxy: open `https://bt.tdgs.org` on phone → install PWA. On projector: press remote button 6 → bt-mode launches fullscreen; navigate + play with remote only.
- rproxy (10.0.10.60) config left to user unless asked (SSE needs `proxy_buffering off`, long timeouts, range passthrough — note will be given).
