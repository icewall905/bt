// One shared EventSource to /api/agent/stream. Events: `state` (state+control+budget) and `agent` (AgentEvent).
import { api } from '../api';
import type { AgentBudget, AgentControl, AgentEvent, AgentState, DownloaderState } from '../types';

const MAX_EVENTS = 400;

class AgentStore {
	state = $state<AgentState>({ state: 'offline' });
	control = $state<AgentControl>({ paused: false, run_now: null, playing_until: null });
	budget = $state<AgentBudget | null>(null);
	downloader = $state<DownloaderState>({ state: 'offline' });
	events = $state<AgentEvent[]>([]);
	connected = $state(false);
	/** Wall clock, ticking once per second, for countdowns. */
	now = $state(Date.now());

	private es: EventSource | null = null;
	private retry = 0;
	private retryTimer: ReturnType<typeof setTimeout> | null = null;
	private listeners = new Set<(e: AgentEvent) => void>();
	private started = false;

	/** Effective state shown in the UI. */
	effective = $derived.by(() => {
		if (!this.connected) return 'offline';
		if (this.control.paused) return 'paused';
		return this.state.state || 'idle';
	});

	start() {
		if (this.started) return;
		this.started = true;
		setInterval(() => (this.now = Date.now()), 1000);
		this.connect();
		document.addEventListener('visibilitychange', () => {
			if (document.visibilityState === 'visible' && !this.connected) this.reconnectNow();
		});
	}

	private connect() {
		this.es?.close();
		const lastId = this.events[0]?.id ?? 0;
		const es = new EventSource(`/api/agent/stream${lastId ? `?after_id=${lastId}` : ''}`);
		this.es = es;
		es.onopen = () => {
			this.connected = true;
			this.retry = 0;
		};
		es.addEventListener('state', (ev) => {
			try {
				const d = JSON.parse((ev as MessageEvent).data);
				if (d.state) this.state = d.state;
				if (d.control) this.control = d.control;
				if (d.budget) this.budget = d.budget;
				if (d.downloader) this.downloader = d.downloader;
				this.connected = true;
			} catch {
				/* ignore malformed */
			}
		});
		es.addEventListener('agent', (ev) => {
			try {
				const e = JSON.parse((ev as MessageEvent).data) as AgentEvent;
				if (this.events.some((x) => x.id === e.id)) return;
				this.events = [e, ...this.events].slice(0, MAX_EVENTS);
				for (const l of this.listeners) l(e);
			} catch {
				/* ignore */
			}
		});
		es.onerror = () => {
			this.connected = false;
			// Browser retries on its own while CONNECTING; if CLOSED (HTTP error), retry ourselves with backoff.
			if (es.readyState === EventSource.CLOSED) this.scheduleRetry();
		};
	}

	private scheduleRetry() {
		if (this.retryTimer) return;
		const delay = Math.min(30000, 2000 * 2 ** this.retry++);
		this.retryTimer = setTimeout(() => {
			this.retryTimer = null;
			this.connect();
		}, delay);
	}

	reconnectNow() {
		if (this.retryTimer) clearTimeout(this.retryTimer);
		this.retryTimer = null;
		this.connect();
	}

	/** Load earlier events (for the Agent page log) once. */
	async backfill() {
		try {
			const evs = await api.agentEvents({ limit: 200 });
			const known = new Set(this.events.map((e) => e.id));
			const merged = [...this.events, ...evs.filter((e) => !known.has(e.id))].sort((a, b) => b.id - a.id);
			this.events = merged.slice(0, MAX_EVENTS);
		} catch {
			/* ignore */
		}
	}

	onEvent(fn: (e: AgentEvent) => void) {
		this.listeners.add(fn);
		return () => this.listeners.delete(fn);
	}

	async pause() {
		this.control = { ...this.control, paused: true };
		try {
			this.control = await api.agentPause();
		} catch {
			this.control = { ...this.control, paused: false };
		}
	}

	async resume() {
		this.control = { ...this.control, paused: false };
		try {
			this.control = await api.agentResume();
		} catch {
			this.control = { ...this.control, paused: true };
		}
	}

	async toggle() {
		return this.control.paused ? this.resume() : this.pause();
	}

	/** Seconds until the real wait end, or null. During backoff the worker wakes every minute for
	 * non-YouTube work, so `until` is only the current 60s chunk — prefer the actual backoff end. */
	secondsLeft = $derived.by(() => {
		const u = this.state.state === 'backoff'
			? (this.state.backoff_until || this.state.until_end || this.state.until)
			: this.state.until;
		if (!u) return null;
		const t = Date.parse(u.endsWith('Z') || u.includes('+') ? u : u + 'Z');
		if (Number.isNaN(t)) return null;
		return Math.max(0, Math.round((t - this.now) / 1000));
	});
}

export const agent = new AgentStore();

export const STATE_LABEL: Record<string, string> = {
	offline: 'AI offline',
	idle: 'AI idle',
	paused: 'AI paused',
	waiting: 'Waiting while you watch',
	sleeping: 'Resting',
	backoff: 'Backing off',
	planning: 'Planning searches',
	searching: 'Searching',
	fetching: 'Fetching details',
	transcript: 'Reading transcript',
	comments: 'Reading comments',
	judging: 'Judging',
	learning: 'Learning from feedback',
	error: 'AI error'
};

export function toneOf(state: string): 'work' | 'rest' | 'bad' | 'paused' | 'off' | 'idle' {
	if (state === 'offline') return 'off';
	if (state === 'paused') return 'paused';
	if (state === 'backoff' || state === 'error') return 'bad';
	if (state === 'sleeping' || state === 'waiting') return 'rest';
	if (state === 'idle') return 'idle';
	return 'work';
}

/** Worker details often repeat the state ("Judging: X"); drop that prefix for display. */
export function cleanDetail(state: string, detail: string | undefined | null): string {
	if (!detail) return '';
	const label = (STATE_LABEL[state] ?? state).toLowerCase();
	const m = /^([^:]{1,40}):\s*(.+)$/.exec(detail);
	if (m && (label.includes(m[1].toLowerCase()) || m[1].toLowerCase().includes(state))) return m[2];
	return detail;
}
