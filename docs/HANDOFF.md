# Handoff — state on 2026-10-25 (wrap-up session)

Read first: `docs/PLAN.md` (design), `docs/CONTRACT.md` (interfaces, ticket ownership, Ticket D spec), `README.md`, `frontend/README.md`.
Workflow: `/home/hnyg/AGENTS.md` (implement → independent review → fix → re-review). Never add AI attribution trailers to commits.

## 2026-10-27 updates
- User-facing rename: categories are now called **playlists** everywhere visible (Settings, Home, search,
  player, agent, Stats). `/settings?tab=playlists` opens the same section; `tab=categories` links still work.
  Routes, API paths, storage and tests' internal ids are unchanged. Backend 158 passed / 4 skipped,
  svelte-check clean, production build OK, Playwright 43/43.
- Storage has a persistent bulk GPU re-encoding queue (`ReencodeJob`). Saved copies stay playable; the
  original is atomically replaced only by a smaller successful output. New downloads have the same size
  safeguard. The HW Transcoding setting controls new downloads independently of bulk jobs.
- `ReencodeResult` records exact sizes for completed encoding attempts; earlier encodes have no reliable
  original size. Stats distinguishes the current library/queue from cumulative measured attempts.
- Statistics now has paged drill-downs (`GET /api/stats/explore`) for overview, category, daily and encoding
  totals, including verdicts, profile context and offline quality filters. Rows count category entries,
  profile watches or encoding attempts as appropriate, rather than deduplicating videos.
- Offline runtime, average duration/file size, channels and longest saved video accompany native SVG
  decision/quality doughnuts and a daily activity chart. Quiet days can be shown in the daily table.
- Candidate playback switches to the candidate's profile before opening its category context.
- **Downloads follow verdicts** (2026-10-27): videos rejected by Family (dislike) or Judge, and ones finished-watched
  by any profile, are pulled from the queue and their saved copies deleted right away (`drop_unwanted` on the
  feedback/history/seen endpoints; in-flight downloads abort via the control hook); the downloader sweeps every
  iteration as a safety net. `sync_queue` never queues watched videos. Pinned saves and copies with a file request
  in the last 10 min (someone may be streaming) are left for a later sweep. Backend 162 passed / 4 skipped.
- **Hover previews** (2026-10-27): every video thumbnail (cards, candidate drawer, agent rows, status pill, stats
  explorer, storage list, up-next, home hero) silently autoplays a muted looping preview on hover: the local copy
  when offline, else DASH ≤540p via Shaka (same proxy as the player; `/fallback` is unusable on modern YouTube —
  no muxed progressive formats). One preview at a time, 350 ms arm delay, teardown on leave. Shared `use:preview`
  action in `$lib/preview.ts`; live test in `tests/content.spec.ts`. svelte-check clean, build OK, Playwright 43/43
  offline + 2/2 with BT_LIVE=1.
- Backend checks: 162 passed, 4 skipped. Frontend type checks and production build pass. Deployed 2026-10-27.

## Done
- **Backend** (`backend/bt`, 106 tests pass, `BT_DATA_DIR=$(mktemp -d) .venv/bin/pytest -q`; `BT_LIVE=1` for network tests)
  - Core API: profiles, categories, feeds, channels, feedback, lessons, history, settings, cookies, auth (optional `BT_PASSWORD`).
  - YouTube layer (`ytdl.py`, `streams.py`, `extras.py`, `api/video.py`): search, video info, DASH MPD + signed range proxy,
    fallback progressive, captions, SponsorBlock/RYD/DeArrow, thumb/avatar cache. **Reviewed: approved** after fixes.
  - AI curator worker (`bt/agent/*`, `llm.py`): plan → discover → enrich (transcript + comments) → judge (vision) → learn
    from feedback; throttle/backoff/pause; abortable LLM calls. **Reviewed: approved.**
  - Agent API + SSE (`api/agent.py`), atomic agent control, `/agent/reset-backoff`.
  - Ticket D backend (offline cache): `bt/downloader/*` (`python -m bt.downloader`), `api/downloads.py`,
    `/api/video/{id}/file`, `download` object on video detail, `offline` flag on cards. **Reviewed: approved** (all
    checklist items: pause/abort, `.part` resume, atomic NFS move, eviction protects pinned/in-progress, startup
    reconcile, path traversal, Range, rate limit, backoff/hourly cap, SIGTERM). Wrap-up fixes after review: flip-time
    re-check so a user DELETE in the scheduling window is never overwritten; post-download move/commit failures now mark
    the row `error` instead of stranding it in `downloading`; dead `state()` removed. Re-review: approved.
- **Frontend** (`frontend/`, SvelteKit SPA + PWA): all screens, spatial nav, OSK, profiles switcher, AI pill + Pause,
  Settings (10 tabs incl. LLM test), player (Shaka + SponsorBlock + recovery), and **Ticket D frontend**: Save offline /
  Remove download (info panel + card menus), offline badge, player plays `/api/video/{id}/file` when done with stream
  fallback and "Offline <height>p" quality label, Settings → Storage tab, Agent page downloader card + progress ring.
  `npm run check` 0 errors, `npm run build` OK, Playwright 19/19 (`npm run test:e2e`, self-contained; `content.spec.ts`
  real-YouTube only with `BT_LIVE=1`). **Reviewed: approved.** All previously flagged review fixes verified fixed
  (watch error-card Back recursion, AiTab steppers single column, focus stealing, LOW items); wrap-up fix after
  re-review: KeysTab third Back now stays on the page (deferred capture unhook). Re-review: approved.
- **Packaging**: Dockerfile (node build → python 3.12 + deno + ffmpeg), `compose.yaml` (bt-api :6645, bt-worker,
  bt-downloader, pot sidecar, `/media` mount), `.env.example`, entrypoint auto-updates yt-dlp.
- **Git**: all work committed and pushed to `git@github.com:icewall905/bt.git` (`main`).
- **Deployed** to `root@10.0.10.73:/root/compose/bt` — see "Deploy state" below.
- **Projector**: `host/bt-mode` installed to `/home/console/bin/bt-mode`, bound to remote button 6 (Ctrl+Shift+Y) in
  `~/.xbindkeysrc`; other `*-mode` scripts now `pkill -f bt-app` (backups `*.bak.bt.<ts>`).

## Deploy state (root@10.0.10.73:/root/compose/bt)
- `.env` has `BT_MEDIA_HOST_DIR=/mnt/local/localstorage/bt` (dir exists, writable, NFS from 10.0.2.85, ~2.7 TB free).
- Sync code with excludes — **never** sync `data/` or `.env` (it overwrites the live SQLite DB and `.secret`):
  `rsync -az --exclude .git --exclude /data --exclude backend/data --exclude .env --exclude node_modules --exclude frontend/build --exclude frontend/.svelte-kit --exclude __pycache__ --exclude .venv --exclude test-results ./ root@10.0.10.73:/root/compose/bt/`
- Nightly copy of `data/` at `/mnt/backup/consolepve/compose/data/bt/data/` (03:00 cron, `compose-backup`).
- `docker compose up -d --build` after rsync; `bt-api`, `bt-worker`, `bt-downloader`, `bt-pot` expected running;
  `curl localhost:6645/api/health` → `{"ok":true}`.
- **GPU (optional)**: `bt-downloader` carries an NVIDIA device reservation (`capabilities: [gpu, video]`)
  for NVENC re-encoding (Settings → Storage → "HW Transcoding"). Needs the nvidia container toolkit on the
  host; on hosts without an NVIDIA GPU, remove the `environment:` + `deploy:` blocks on `bt-downloader` and
  leave the toggle off — downloads are then kept exactly as yt-dlp saved them.

## Remaining / to do (physical only)
1. **Projector test**: press remote button 6 → `bt-mode` opens Chromium kiosk at `http://localhost:6645`;
   navigate + play with remote only; confirm audio on HDMI and that other modes close bt-app.
   Log: `/home/console/.local/share/bt-mode.log`.
2. **PWA install** from a phone at `https://bt.tdgs.org` (rproxy verified serving; HTTP/2 via traefik).

## Verified end-to-end on host (2026-10-25, wrap-up session)
- All four services up: `bt-api` (healthy, `:6645`), `bt-worker`, `bt-downloader`, `bt-pot`; `/api/health` OK locally
  and via `https://bt.tdgs.org`.
- Curator loop live: plan → fetch → transcript → comments → judge → accept/reject events streaming.
- Throttling confirmed: budget 90/120 per hour (downloads included), jittered "sleeping" waits between requests.
- Feedback → lesson verified live: "mean to the cat" on a cat video → lesson learned in ~50 s ("reject any clip where
  the animal is startled, stressed, embarrassed, or mocked for laughs…"), channel trust −0.3, and the very next cat
  video from that channel was **rejected (28)** — previously a similar one was accepted (68).
- Downloads land in `/mnt/local/localstorage/bt` (`<id[:2]>/<id>.mp4`, 1080p, 326 MB first file) with `.tmp/*.part`
  staging; 15 queued, round-robin across categories; SSE `state.downloader` reporting progress.
- Offline playback verified at the API level: `/api/video/{id}/file` serves 206 for byte ranges, video detail carries
  `download: {status: done, height: 1080, …}` and `offline: true`. (Player UI path is covered by Playwright; the
  projector test above is the last physical confirmation.)

## Known accepted limitations (from final reviews, all LOW)
- Card menus show "Save offline" even for videos already queued/downloading (cards only carry the `offline` boolean;
  fixing needs download status on card payloads). Harmless: re-click just pins.
- Watch-page OfflineButton progress is a snapshot from page load; ticks only on the Agent page / Storage tab.
- Two simultaneously dirty Save bars can overlap on the AI tab (edge case).
- `api.ts` downloads normalizer keeps a few dead shape branches.
- Pause during the ffmpeg merge phase takes effect only after the merge completes (progress-hook driven).
- Eviction does not exempt a video currently being played (only pinned/in-progress); mid-play eviction 404s later
  Range requests → player error card. `playing_until` gate available if it ever matters.

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
