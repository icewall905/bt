# BetterTube frontend

SvelteKit 2 + Svelte 5 (runes) + TypeScript SPA, built with `adapter-static` into `frontend/build`
(`index.html` SPA fallback, `ssr = false`, no prerendering). FastAPI serves it (see `backend/bt/main.py`).
Made for a 1920×1080 projector driven only by an RF remote, but fully usable with touch and mouse.

## Commands

```sh
npm install
npm run dev        # Vite on :5173, proxies /api → http://localhost:6699 (override with BT_BACKEND=…)
npm run check      # svelte-kit sync + svelte-check (must be 0 errors)
npm run build      # → build/
npm run icons      # regenerate static/icons/*.png from static/favicon.svg (needs sharp)
npm run test:e2e   # builds if needed, starts the backend on a free port with a throwaway data dir, runs Playwright
```

Backend for local integration (from `backend/`):

```sh
BT_DATA_DIR=/tmp/bt-dev BT_STATIC_DIR=../frontend/build .venv/bin/uvicorn bt.main:app --port 6699
```

Playwright uses the installed Google Chrome (`channel: 'chrome'`, override with `PW_CHANNEL`) and the
same `--autoplay-policy=no-user-gesture-required` flag as the kiosk. `scripts/e2e.sh` (behind
`npm run test:e2e`) gives every run a fresh `BT_DATA_DIR`; the tests also reset state themselves
(`tests/helpers.ts`), so never point `BT_URL` at real data. Suites: `smoke` (keyboard-only tour),
`settings-walk` (every control on every Settings tab reachable by arrows), `home-focus` (no focus
stealing), `player-error` (Back leaves a broken video). `tests/content.spec.ts` uses real YouTube and
only runs with `BT_LIVE=1`. Screenshots land in `screenshots/` (gitignored).

## Layout

```
src/
  app.html, app.css            design tokens (colours, type scale via clamp(), focus ring) + base styles
  service-worker.ts            precache build+static; cache-first /api/thumb/*; never caches other /api
  routes/
    +layout.ts                 ssr=false, prerender=false
    +layout.svelte             boot (auth, profiles, SSE), top bar, global dialogs, OSK, toasts, back handling
    +page.svelte               Home: hero (top pick), Continue watching, one row per category, subscriptions
    category/[id]              Picked / In review / Rejected tabs, "why picked/rejected", Find more now
    watch/[id]?c=catId         Shaka player, overlay controls, SponsorBlock, captions, info panel, end screen
    search                     search field + on-screen keyboard grid, results with "Add to category…"
    subscriptions, channel/[id]
    agent                      live status, countdown, YouTube budget, queues, live log → candidate drawer
    settings?tab=…             categories, memory, ai (LLM + curator + limits), player, sponsorblock,
                               extras, cookies, profiles, keys (remote test)
  lib/
    api.ts                     typed client for every endpoint; X-Profile-Id header; 401 → login; error toasts
    types.ts                   response shapes
    nav/                       spatial navigation engine (below)
    stores/                    session (auth/profiles/categories/settings), agent (SSE), toast, dialogs
    player/                    lazy Shaka loader (DASH-only build), SponsorBlock segment prep
    settings/                  settings tabs + SettingsDraft (dirty tracking/save per key)
    components/                cards, rows, modal, status pill, profile picker/editor, OSK, form controls…
```

## Spatial navigation (`src/lib/nav`)

Every remote-reachable element opts in with the `focusable` action; it receives real DOM focus.

```svelte
<script>
  import { focusable, navScope } from '$lib/nav';
</script>

<button use:focusable={{ group: 'row-3', onSelect: play }}>Play</button>

<div use:navScope={{ onBack: close }}>   <!-- focus trap; Back calls onBack -->
  <button use:focusable={{ autofocus: true, onSelect: save }}>Save</button>
</div>
```

`FocusOpts`:

| option | meaning |
|---|---|
| `group` | row/section id. Left/Right stays inside the group; moving Up/Down *into* a group restores that group's last focused element (`memory: false` turns this off for grids such as the keyboard). |
| `id` | stable id so focus can be restored when you come back to the route (falls back to group + index). |
| `onSelect` | Enter/OK **and** click/tap. Links without `onSelect` just navigate. |
| `onKey(key, e)` | per-element handler, return `true` to consume (`'left'`, `'right'`, `'select'`, …), e.g. sliders and the seek bar. |
| `autofocus` | initial focus of the view or scope. When several exist the last one wins (a form beats a side menu). |
| `scroll` | `'center'` / `'nearest'` / `'none'`. Default: centre inside `[data-nav-row]` (carousels) and `[data-nav-center]` (card grids), otherwise nearest. |
| `osk` | text inputs: Enter opens the on-screen keyboard (default `true`). |

Engine behaviour:

- Arrows pick the geometrically nearest candidate in that direction. Horizontal moves prefer the same
  group, then the same visual line; inside a carousel (`[data-nav-row]`) they never jump to another row.
  The top bar is marked `data-nav-skip-initial` and never wins a horizontal fallback from content.
- Enter = `click()`; Space / MediaPlayPause go to global handlers first (player), otherwise act as Enter.
- Back (Backspace, Escape, BrowserBack): top scope's `onBack`, else router back (only through entries this
  app created; otherwise Home).
- Focus memory per route (`pathname+search`) and per group; restored when data arrives (up to 2.5 s).
- Zones: `data-nav-zone="…"` on a container keeps Up/Down inside it (e.g. Settings side menu vs. its
  content); zone-less chrome such as the top bar stays reachable.
- Once the user has pressed a key on a route, the engine never moves focus by itself (no late restores or
  upgrades); it only re-places focus when the focused element disappears or focus falls to `<body>`.
- Scroll areas: `use:focusable={{ onKey: scrollByKeys }}` makes Up/Down scroll the element until its end.
- Global key handlers: `nav.handleKeys((key, e) => boolean)` (used by the player and the key-capture page).
  Raw keys: `nav.onRawKey(fn)`.
- Input modality: `html[data-modality=keys|pointer]`. The glowing focus ring + scale is shown only for keys;
  touch/mouse users never get automatic focus. Mouse hover never moves focus.
- Text inputs: physical keyboards type normally. With the remote, Enter opens the OSK (`osk.svelte.ts`,
  rendered by `OskOverlay.svelte`), which writes back via `input` events so `bind:value` works. Left/Right
  leave the input at the caret edges, Up/Down leave single-line inputs, Backspace on an empty input = Back.

## Player

`/watch/[id]` loads `/api/video/{id}/manifest.mpd` in Shaka (`shaka-player.dash` build, loaded lazily).
Recovery: manifest 404/other load error → `/api/video/{id}/fallback` (progressive); a 403 from
`/api/proxy/…` → reload the manifest once at the current position; a decoder error (3016) → reload once
pinned to one quality; then fallback; then an error card with "Try again". 409 = live (unsupported).
While the manifest is prepared (5–15 s on first play) a blurred thumbnail with "Preparing video…" shows.

History is saved every 10 s while playing, on pause, on exit/hidden (`keepalive`), and as finished at the
end. `POST /api/agent/playing` heartbeat every 60 s while playing. Remote: Left/Right on the seek bar seek
±10 s, Up/Down move between rows, Down from the button row opens details, Space toggles, Back hides the
controls first, then leaves. SponsorBlock segments are coloured on the bar; actions per category from
settings (`skip` auto-skips with a toast, `ask` shows a focused Skip button, `show` marks only).

## Offline copies (Ticket D)

- `video.offline` shows an "Offline" badge on cards; "Save offline / Remove download" (`OfflineButton`) sits in
  the player info panel, the candidate drawer and the action rows of category and search cards.
- The player plays `/api/video/{id}/file` when `download.status == "done"` (quality shows "Offline 1080p"). If
  the detail call fails (YouTube blocked) it probes the file with a 1-byte Range request first. A file error
  falls back to streaming at the same position.
- Settings, Storage: `cache` settings, usage bar, saved list with progress/cancel/delete, Clear all
  (`DELETE /api/downloads`). Agent page: downloader card. Top bar pill: progress ring while downloading.
  Downloader state comes from the SSE `state` event (`downloader`).
- `tests/offline.spec.ts` seeds a generated 20 s clip as a finished download in the throwaway data dir
  (needs `ffmpeg`).

## PWA

`static/manifest.webmanifest` (standalone, dark, 192/512 + maskable icons) and `src/service-worker.ts`
(registered automatically by SvelteKit). The backend serves `service-worker.js` and the manifest with
`Cache-Control: no-cache`.
