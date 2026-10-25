# BetterTube (bt)

Self-hosted, ad-free YouTube front-end with a background AI curator.

- **No ads by construction** – the YouTube player is never embedded; streams are resolved with yt-dlp and
  proxied (DASH via Shaka Player). SponsorBlock, Return YouTube Dislike, optional DeArrow.
- **Family profiles** – switcher top-right; each person has their own categories, feedback, AI memory,
  subscriptions and history.
- **AI curator** – a slow, throttled background worker asks your local LLM (OpenAI-compatible) to plan
  searches per category, reads metadata, transcript, top comments and thumbnail, judges fit, and learns
  from feedback ("they were mean to the cat") as editable *lessons*. Live status + pause button always visible.
- **10-foot UI** – remote-control spatial navigation (arrows / OK / back), on-screen keyboard, installable PWA.

## Layout
```
backend/bt/      FastAPI api (+ serves SPA), agent worker (python -m bt.agent), yt-dlp layer
frontend/        SvelteKit SPA + PWA
host/            projector desktop integration (bt-mode, remote button 6)
docs/PLAN.md     design;  docs/CONTRACT.md  interfaces + ticket ownership
```

## Run
```bash
cp .env.example .env   # set BT_PASSWORD
docker compose up -d --build
```
Services: `bt-api` (:6645), `bt-worker`, `pot` (PO-token provider for yt-dlp). Data in `./data`.

Production: `root@10.0.10.73:/root/compose/bt`, exposed as `https://bt.tdgs.org` via traefik on 10.0.10.60.

## Dev
```bash
cd backend && uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements.txt
BT_DATA_DIR=/tmp/bt-dev .venv/bin/uvicorn bt.main:app --port 6699 --reload
BT_DATA_DIR=/tmp/bt-dev .venv/bin/python -m bt.agent
.venv/bin/pytest            # BT_LIVE=1 for network tests
cd frontend && npm ci && npm run dev
```

## Projector
`host/install-desktop.sh` (as root on the projector host) installs `/home/console/bin/bt-mode`
and binds it to remote button 6 (Ctrl+Shift+Y via input-remapper → xbindkeys).
