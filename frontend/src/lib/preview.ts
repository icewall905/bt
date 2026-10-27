// Hover previews: a silent, looping DASH playback that fades in over a thumbnail while the pointer
// rests on it — on every video card, the candidate drawer, agent rows, stats, storage, up-next and
// the home hero. Uses Shaka (the same DASH/proxy pipeline as the player, capped at 540p) or the
// local copy when the video is saved offline. Media segments are never logged against the YouTube
// budget, quick sweep-overs never start anything (350 ms arm delay), only one preview plays at a
// time, and the stream is torn down the moment the pointer leaves.

import { api } from './api';

const DELAY_MS = 350; // quick sweep-overs must not start fetches
const FADE_MS = 160;
const PREVIEW_HEIGHT = 540; // preview bits are not bits to treasure; the player offers full quality

// Feed reshuffles can replace a card component while the pointer sits parked on it; a fresh
// action would never see a pointerenter again. Track the pointer once and let (re)created
// actions arm themselves when the pointer is already inside their trigger element.
let px = -1;
let py = -1;
let pointerTracked = false;
function trackPointer() {
	if (pointerTracked || typeof document === 'undefined') return;
	pointerTracked = true;
	document.addEventListener('pointermove', (e) => { px = e.clientX; py = e.clientY; }, { passive: true, capture: true });
}

function pointerOver(el: HTMLElement | null): boolean {
	if (!el || !el.isConnected || px < 0 || py < 0) return false;
	const r = el.getBoundingClientRect();
	return px >= r.left && px <= r.right && py >= r.top && py <= r.bottom;
}

export interface PreviewOpts {
	id: string;
	/** saved offline: play the local mp4 instead of streaming DASH */
	offline?: boolean;
	/** where enter/leave are watched; default: the node itself */
	listenOn?: HTMLElement | null;
	/** where the video overlay is inserted; default: the node itself */
	host?: HTMLElement | null;
}

const CSS = `.bt-hover-pv{position:absolute;inset:0;z-index:0;width:100%;height:100%;object-fit:cover;border-radius:inherit;pointer-events:none;background:#000;opacity:0;transition:opacity .35s ease}
.bt-hover-pv.ready{opacity:1}
.bt-hover-pv.bye{opacity:0;transition:opacity ${FADE_MS}ms ease}`;

let injected = false;
function injectCss() {
	if (injected) return;
	injected = true;
	const st = document.createElement('style');
	st.textContent = CSS;
	document.head.appendChild(st);
}

interface Run {
	owner: symbol;
	el: HTMLVideoElement;
	player?: { destroy: () => Promise<void> };
}

let current: Run | null = null;

/** Stop the running preview (or only the given one, when a newer preview already took over). */
function stop(only?: HTMLVideoElement) {
	if (only && (!current || current.el !== only)) return;
	const run = current;
	current = null;
	if (!run) return;
	run.el.classList.remove('ready');
	run.el.classList.add('bye'); // brief fade-out, then teardown so the stream is really aborted
	window.setTimeout(() => {
		run.el.pause();
		run.player?.destroy().catch(() => (run.player as { release?: () => void } | undefined)?.release?.());
		run.el.removeAttribute('src');
		run.el.load();
		run.el.remove();
	}, FADE_MS + 30);
}

async function start(host: HTMLElement, opts: PreviewOpts, owner: symbol) {
	if (!opts.id) return;
	stop(); // at most one preview everywhere at a time
	if (document.visibilityState !== 'visible') return;
	injectCss();

	const el = document.createElement('video');
	el.className = 'bt-hover-pv';
	el.setAttribute('muted', ''); // autoplay policies key off the attribute
	el.muted = true;
	el.autoplay = true;
	el.playsInline = true;
	el.setAttribute('aria-hidden', 'true');
	const run: Run = { el, owner };
	el.addEventListener('playing', () => el.classList.add('ready'), { once: true });
	el.addEventListener('error', () => stop(el));
	// The image may form a stacking context (for example, a hover transform). Insert the
	// video after it so the frame paints above the still, but before badges and summaries.
	const still = Array.from(host.children).find((child) => child.tagName === 'IMG');
	if (still) still.after(el);
	else host.prepend(el);
	current = run;

	try {
		if (opts.offline) {
			// Saved copy: a plain mp4 plays without DASH.
			el.loop = true;
			el.src = api.fileUrl(opts.id);
			await el.play().catch(() => {});
			return;
		}
		const { loadShaka } = await import('$lib/player/shaka');
		const shaka = await loadShaka();
		if (current !== run) return; // the pointer left / another preview took over meanwhile
		if (!shaka.Player.isBrowserSupported()) throw new Error('no MSE');
		const player = new shaka.Player();
		await player.attach(el);
		if (current !== run) {
			player.destroy().catch(() => {});
			return;
		}
		run.player = player;
		player.configure({
			streaming: { bufferingGoal: 8, rebufferingGoal: 1, bufferBehind: 5 },
			abr: { enabled: true, restrictions: { maxHeight: PREVIEW_HEIGHT } },
		});
		await player.load(api.manifestUrl(opts.id, PREVIEW_HEIGHT), undefined, 'application/dash+xml');
		if (current !== run) return;
		el.loop = true;
		await el.play().catch(() => {});
	} catch {
		stop(el); // unavailable/live/slow: stay on the static thumbnail
	}
}

export function preview(node: HTMLElement, opts: PreviewOpts) {
	trackPointer();
	const owner = Symbol("preview action");
	let cfg = opts;
	let listen: HTMLElement | null = null;
	let timer: number | undefined;

	const canHover = () => window.matchMedia('(hover: hover)').matches;

	function enter() {
		if (timer !== undefined || !canHover()) return;
		timer = window.setTimeout(() => {
			timer = undefined;
			const host = cfg.host ?? node;
			if (host && host.isConnected) void start(host, cfg, owner);
		}, DELAY_MS);
	}

	function leave() {
		if (timer !== undefined) {
			clearTimeout(timer);
			timer = undefined;
		}
		if (current?.owner === owner) stop(current.el);
	}

	function rewire() {
		const t = cfg.listenOn ?? node;
		if (t === listen) return;
		if (listen) {
			listen.removeEventListener('pointerenter', enter);
			listen.removeEventListener('pointerleave', leave);
		}
		listen = t;
		listen.addEventListener('pointerenter', enter);
		listen.addEventListener('pointerleave', leave);
	}

	rewire();
	if (pointerOver(cfg.listenOn ?? node)) enter(); // pointer parked here already (e.g. after a feed reshuffle)
	return {
		update(p: PreviewOpts) {
			// Feed/row refreshes rebuild card props with the SAME video under the pointer all the time
			// (agent 'accept' events trigger home/category reloads). Only a real target change may
			// interrupt a running preview, otherwise hover previews tear down mid-motion forever.
			const same = p.id === cfg.id && !!p.offline === !!cfg.offline;
			const wasArmed = timer !== undefined || current?.owner === owner;
			cfg = p;
			rewire();
			if (same) {
				// nothing runs and nothing is armed, but the pointer is sitting on us: re-arm
				if (!wasArmed && pointerOver(cfg.listenOn ?? node)) enter();
				return;
			}
			leave();
			if (wasArmed || pointerOver(cfg.listenOn ?? node)) enter();
		},
		destroy() {
			leave();
			if (listen) {
				listen.removeEventListener('pointerenter', enter);
				listen.removeEventListener('pointerleave', leave);
				listen = null;
			}
		},
	};
}
