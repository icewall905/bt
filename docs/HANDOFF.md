# Handoff — state on 2026-10-25

Read first: `docs/PLAN.md` (design), `docs/CONTRACT.md` (interfaces, ticket ownership, Ticket D spec), `README.md`, `frontend/README.md`.
Workflow: `/home/hnyg/AGENTS.md` (implement → independent review → fix → re-review). Never add AI attribution trailers to commits.

## Done
- **Backend** (`backend/bt`, 106 tests pass, `BT_DATA_DIR=$(mktemp -d) .venv/bin/pytest -q`; `BT_LIVE=1` for network tests)
  - Core API: profiles, categories, feeds, channels, feedback, lessons, history, settings, cookies, auth (optional `BT_PASSWORD`).
  - YouTube layer (`ytdl.py`, `streams.py`, `extras.py`, `api/video.py`): search, video info, DASH MPD + signed range proxy,
    fallback progressive, captions, SponsorBlock/RYD/DeArrow, thumb/avatar cache. **Reviewed: approved** after fixes.
  - AI curator worker (`bt/agent/*`, `llm.py`): plan → discover → enrich (transcript + comments) → judge (vision) → learn
    from feedback; throttle/backoff/pause; abortable LLM calls. **Reviewed: approved.**
  - Agent API + SSE (`api/agent.py`), atomic agent control, `/agent/reset-backoff`.
- **Packaging**: Dockerfile (node build → python 3.12 + deno + ffmpeg), `compose.yaml` (bt-api :6645, bt-worker,
  bt-downloader, pot sidecar, `/media` mount), `.env.example`, entrypoint auto-updates yt-dlp.
- **Deployed** to `root@10.0.10.73:/root/compose/bt` (old build — **without** downloader/frontend fixes). Reachable at
  `https://bt.tdgs.org` (LAN-only DNS → traefik 10.0.10.60). Manifest verified 144p–1080p on host.
- **Projector**: `host/bt-mode` installed to `/home/console/bin/bt-mode`, bound to remote button 6 (Ctrl+Shift+Y) in
  `~/.xbindkeysrc`; other `*-mode` scripts now `pkill -f bt-app` (backups `*.bak.bt.<ts>`). Not yet launched/tested on the projector.
- **Frontend** (`frontend/`, SvelteKit SPA + PWA): all screens, spatial nav, OSK, profiles switcher, AI pill + Pause, Settings
  (10 tabs incl. LLM test), player (Shaka + SponsorBlock + recovery). `npm run check` 0 errors, `npm run build` OK.
- **Ticket D backend** (offline cache): `bt/downloader/*` (`python -m bt.downloader`), `api/downloads.py`,
  `/api/video/{id}/file`, `download` object on video detail, `offline` flag on cards. Tests pass; live download verified locally.

## Missing / to do (in order)
1. **Verify frontend review fixes.** The frontend agent was stopped while finishing these (likely done, unverified). Check each
   against the code and re-run an independent review:
   - HIGH: watch error card `navScope onBack: exit` → `nav.back()` infinite recursion (`src/routes/watch/[id]/+page.svelte`); user
     must be able to leave an unplayable video with Back.
   - MED: AI tab throttle Steppers in left column unreachable by remote (`src/lib/settings/AiTab.svelte`).
   - MED: intermittent focus stealing on Home after navigation (`src/lib/nav/engine.ts` ensure/pendingRestore; SvelteKit focus reset).
   - LOW: Settings initial focus/side-tab switching on focus; `/settings?tab=categories&new=1` should focus Name;
     KeysTab capture strands focus + `idle` timeout not cleared; stacked sticky Save bars on AI tab; info-panel description
     scrollable by remote; cookies file input focusable.
   - Make `tests/smoke.spec.ts` self-contained and exclude `content.spec.ts` (real YouTube) unless `BT_LIVE=1`.
2. **Ticket D frontend** (not started) — spec in CONTRACT.md "Ticket D": Save offline / Remove download (info panel + card
   menu), offline badge on cards, player plays `/api/video/{id}/file` when `download.status=="done"` (fallback to stream),
   Settings → Storage tab (`PUT /api/settings/cache`, usage bar, downloads list, Clear all = `DELETE /api/downloads`),
   Agent page downloader card from SSE `state.downloader`, progress ring on the top-bar pill.
   API shapes: `GET /api/downloads` → `{items:[{video_id,status,progress,height,size_bytes,pinned,error,attempts,created_at,
   finished_at,last_played_at,video}], totals:{used_bytes,max_bytes,counts}, state}`; `POST /api/downloads {video_id}`;
   `DELETE /api/downloads/{id}`; `DELETE /api/downloads`.
3. **Review Ticket D backend** (review was interrupted): pause/abort, `.part` resume, atomic move on NFS
   (`/mnt/local/localstorage/bt` is NFS from 10.0.2.85; staging `.tmp` is under MEDIA_DIR so same fs), eviction never touching
   pinned/in-progress, startup reconcile safety, path traversal, Range, rate limit, backoff/hourly cap, SIGTERM.
   Known gap: `api/agent.py` candidate_detail calls `candidate_out(c, v)` without `offline=` (1 extra query, fine).
4. **Commit + push** to `git@github.com:icewall905/bt.git` (local commits exist on `main`, nothing pushed yet).
5. **Redeploy**: `rsync` repo → `root@10.0.10.73:/root/compose/bt` (exclude .git, node_modules, .venv, frontend/build, data, .env),
   ensure `.env` has `BT_MEDIA_HOST_DIR=/mnt/local/localstorage/bt` (dir exists, writable by root), then
   `docker compose up -d --build`. Check `docker compose ps`, logs of bt-downloader, `curl localhost:6645/api/health`.
6. **End-to-end on host** (PLAN.md Verification): create "Videos with kids" + "Grownups" categories in two profiles, watch the
   agent pill/Agent page, confirm throttling in YtRequest counts, give feedback "mean to the cat" → lesson appears and affects
   judgments, downloads appear in `/mnt/local/localstorage/bt`, offline playback works.
7. **Projector test**: press remote button 6 → `bt-mode` opens Chromium kiosk at `http://localhost:6645`; navigate + play with
   remote only; confirm audio on HDMI and that other modes close bt-app. Log: `/home/console/.local/share/bt-mode.log`.
8. **PWA install** from a phone at `https://bt.tdgs.org`.

## Known risks / notes
- yt-dlp DASH ranges come from a private yt-dlp hook (`ytdl.attach_ranges`); if an update breaks it, mp4 falls back to range
  probing and VP9/WebM is dropped (logged warning). Entrypoint auto-upgrades yt-dlp (`BT_YTDLP_AUTOUPDATE=1`).
- PO-token sidecar runs but yt-dlp didn't request tokens in tests; some videos (e.g. dQw4w9WgXcQ) 403 from this IP without
  them → manifest 404 → player fallback/error card.
- Shaka 3016 decode error once seen on BYVZh5kqaFg (not reproduced; audio sets now single-codec). If it recurs, log
  `error.detail.data` and consider splitting H.264 Main/High profiles.
- LLM: `currentmodel` on `http://10.0.10.23:8080/v1`; thinking models may exhaust tokens → automatic retry with
  `enable_thinking=false`; `llm.thinking=false` setting available.
- No password by default (`BT_PASSWORD` empty) because bt.tdgs.org resolves only on the LAN.
