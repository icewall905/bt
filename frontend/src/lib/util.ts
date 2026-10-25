export function fmtDuration(s: number | null | undefined): string {
	if (!s || s < 0 || !Number.isFinite(s)) return '0:00';
	s = Math.floor(s);
	const h = Math.floor(s / 3600);
	const m = Math.floor((s % 3600) / 60);
	const sec = s % 60;
	const mm = h ? String(m).padStart(2, '0') : String(m);
	return `${h ? h + ':' : ''}${mm}:${String(sec).padStart(2, '0')}`;
}

export function fmtCount(n: number | null | undefined): string {
	if (n == null) return '–';
	if (n >= 1e9) return (n / 1e9).toFixed(n >= 1e10 ? 0 : 1).replace(/\.0$/, '') + 'B';
	if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, '') + 'M';
	if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(/\.0$/, '') + 'K';
	return String(n);
}

/** Parse naive-UTC ISO timestamps from the backend. */
export function parseTs(ts: string | null | undefined): number | null {
	if (!ts) return null;
	const t = Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(ts) ? ts : ts + 'Z');
	return Number.isNaN(t) ? null : t;
}

export function timeAgo(ts: string | null | undefined, now = Date.now()): string {
	const t = parseTs(ts);
	if (t == null) return '';
	const d = Math.max(0, (now - t) / 1000);
	if (d < 45) return 'just now';
	if (d < 3600) return `${Math.round(d / 60)} min ago`;
	if (d < 86400) return `${Math.round(d / 3600)} h ago`;
	if (d < 86400 * 30) return `${Math.round(d / 86400)} d ago`;
	if (d < 86400 * 365) return `${Math.round(d / (86400 * 30))} mo ago`;
	return `${Math.round(d / (86400 * 365))} y ago`;
}

export function clockTime(ts: string | null | undefined): string {
	const t = parseTs(ts);
	if (t == null) return '';
	return new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function fmtCountdown(sec: number | null): string {
	if (sec == null) return '';
	if (sec >= 3600) return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
	if (sec >= 60) return `${Math.floor(sec / 60)}m ${String(sec % 60).padStart(2, '0')}s`;
	return `${sec}s`;
}

export function clamp(v: number, lo: number, hi: number) {
	return Math.min(hi, Math.max(lo, v));
}

export const SB_COLORS: Record<string, string> = {
	sponsor: '#00d26a',
	selfpromo: '#ffd60a',
	interaction: '#cc00ff',
	intro: '#00ffff',
	outro: '#0202ed',
	preview: '#008fd6',
	filler: '#7300ff',
	music_offtopic: '#ff9900',
	poi_highlight: '#ff1684',
	exclusive_access: '#008a5c',
	chapter: '#ffffff'
};

export const SB_LABELS: Record<string, string> = {
	sponsor: 'Sponsor',
	selfpromo: 'Self-promotion',
	interaction: 'Like/subscribe reminder',
	intro: 'Intro',
	outro: 'Outro / end cards',
	preview: 'Preview / recap',
	filler: 'Filler tangent',
	music_offtopic: 'Non-music section',
	poi_highlight: 'Highlight',
	exclusive_access: 'Exclusive access'
};

export const PALETTE = ['#7c5cff', '#ff6b9a', '#ffb84d', '#3ddc97', '#4cc3ff', '#ff7a45', '#c77dff', '#f4e04d', '#5ee6d0', '#ff4d6d'];

export function isVideo(v: unknown): v is import('./types').Video {
	return !!v && typeof v === 'object' && 'title' in v;
}

export function fmtBytes(n: number | null | undefined): string {
	if (!n || n < 0) return '0 B';
	const u = ['B', 'KB', 'MB', 'GB', 'TB'];
	let i = 0;
	while (n >= 1000 && i < u.length - 1) (n /= 1000), i++;
	return `${n >= 100 || i === 0 ? Math.round(n) : n.toFixed(1)} ${u[i]}`;
}
