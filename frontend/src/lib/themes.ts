/** The first palette is the original BetterTube appearance. The other themes
 * only override visual tokens: playback, settings and profile colours are unchanged. */
export interface Theme {
	id: string; name: string; description: string;
	bg: string; bg1: string; bg2: string; surface: string; accent: string; accentInk: string;
	ai: string; text: string; muted: string; faint: string;
}

export const THEMES: Theme[] = [
	{ id: 'projector', name: 'Projector', description: 'The original violet room and warm amber.', bg: '#0a0817', bg1: '#110e26', bg2: '#1a1638', surface: '#1b1740', accent: '#ffb547', accentInk: '#1c1205', ai: '#9d86ff', text: '#f0edff', muted: '#aaa4d2', faint: '#716b9c' },
	{ id: 'ocean', name: 'Abyss', description: 'Deep-sea navy lit by bioluminescent teal.', bg: '#060b12', bg1: '#0a121c', bg2: '#101b28', surface: '#142333', accent: '#4fd1c5', accentInk: '#03201d', ai: '#7aa2ff', text: '#e3edf5', muted: '#93a7b8', faint: '#62788a' },
	{ id: 'forest', name: 'Moss', description: 'Night forest floor with fresh lime and sand.', bg: '#070b08', bg1: '#0c120e', bg2: '#121a14', surface: '#18241b', accent: '#a3d977', accentInk: '#13200a', ai: '#d9b87a', text: '#e4ecdf', muted: '#9cad9a', faint: '#687a6b' },
	{ id: 'ember', name: 'Ember', description: 'Smouldering charcoal with glowing orange.', bg: '#0c0807', bg1: '#140e0c', bg2: '#1c1411', surface: '#261b16', accent: '#ff7a3d', accentInk: '#2a0e02', ai: '#f2c46d', text: '#f3e9e3', muted: '#b8a397', faint: '#806e63' },
	{ id: 'midnight', name: 'Midnight', description: 'Ink-black blue with starlight periwinkle.', bg: '#05060d', bg1: '#0a0c18', bg2: '#101325', surface: '#161a32', accent: '#8fb4ff', accentInk: '#0b1630', ai: '#c39bff', text: '#e6e9fa', muted: '#9ba2c7', faint: '#666d94' },
	{ id: 'slate', name: 'Graphite', description: 'Quiet monochrome with a crisp white edge.', bg: '#0a0a0b', bg1: '#111113', bg2: '#18181b', surface: '#202024', accent: '#ededef', accentInk: '#111113', ai: '#8b9bb4', text: '#ededef', muted: '#a1a1aa', faint: '#6e6e78' },
	{ id: 'rose', name: 'Velvet', description: 'Dark wine velvet with soft rose and lilac.', bg: '#0e070b', bg1: '#160b12', bg2: '#1f1019', surface: '#2a1622', accent: '#ff8fb1', accentInk: '#3a0a1d', ai: '#c9a0ff', text: '#f6e8ef', muted: '#c09aab', faint: '#88667d' },
	{ id: 'aurora', name: 'Aurora', description: 'Polar night with mint and violet lights.', bg: '#050b0c', bg1: '#091214', bg2: '#0e1b1e', surface: '#132528', accent: '#5ef0b0', accentInk: '#04261a', ai: '#b18cff', text: '#e2f3ef', muted: '#92b3ad', faint: '#5e7d78' },
	{ id: 'copper', name: 'Copper', description: 'Dark walnut, burnished copper and verdigris.', bg: '#0b0907', bg1: '#13100c', bg2: '#1b1611', surface: '#251e17', accent: '#e0955a', accentInk: '#2b1405', ai: '#7fbfb0', text: '#f1e9df', muted: '#b5a593', faint: '#7d6f5f' },
	{ id: 'noir', name: 'Noir', description: 'True black, silver type and a single red.', bg: '#050505', bg1: '#0b0b0c', bg2: '#121214', surface: '#1a1a1d', accent: '#ff4d5e', accentInk: '#2a0006', ai: '#9aa0b5', text: '#f0f0f0', muted: '#a3a3a8', faint: '#6c6c72' },
	{ id: 'lagoon', name: 'Lagoon', description: 'Dark tidewater with warm coral and cyan.', bg: '#04090d', bg1: '#081218', bg2: '#0d1b23', surface: '#12262f', accent: '#ff9e7a', accentInk: '#2e1006', ai: '#5cc8e0', text: '#e4f1f4', muted: '#92b0b8', faint: '#5f7d86' }
];

const TOKENS = ['--bg-0', '--bg-1', '--bg-2', '--surface', '--surface-solid', '--surface-2', '--surface-hi', '--line', '--line-strong', '--text', '--muted', '--faint', '--accent', '--accent-2', '--accent-ink', '--accent-glow', '--ai', '--ambient-1', '--ambient-2', '--ambient-3', '--modal-top', '--modal-bottom', '--overlay-surface', '--overlay-surface-deep', '--keyboard-surface', '--toast-surface', '--status-pop-surface', '--savebar-surface'];

export function applyTheme(id: string | null | undefined) {
	const theme = THEMES.find((t) => t.id === id) ?? THEMES[0];
	const root = document.documentElement;
	root.dataset.theme = theme.id;
	for (const token of TOKENS) root.style.removeProperty(token);
	if (theme.id !== 'projector') {
		const mix = (color: string, amount: number, into = 'transparent') => `color-mix(in srgb, ${color} ${amount}%, ${into})`;
		const tokens: Record<string, string> = {
			'--bg-0': theme.bg, '--bg-1': theme.bg1, '--bg-2': theme.bg2,
			'--surface': mix(theme.surface, 70), '--surface-solid': theme.surface,
			'--surface-2': mix(theme.surface, 85, theme.ai), '--surface-hi': mix(theme.surface, 65, theme.ai),
			'--line': mix(theme.text, 11), '--line-strong': mix(theme.text, 24),
			'--text': theme.text, '--muted': theme.muted, '--faint': theme.faint,
			'--accent': theme.accent, '--accent-2': mix(theme.accent, 75, 'white'), '--accent-ink': theme.accentInk,
			'--accent-glow': mix(theme.accent, 48), '--ai': theme.ai,
			'--ambient-1': mix(theme.ai, 14), '--ambient-2': mix(theme.accent, 6), '--ambient-3': mix(theme.ai, 10),
			'--modal-top': mix(theme.surface, 95), '--modal-bottom': mix(theme.bg1, 97),
			'--overlay-surface': mix(theme.surface, 96), '--overlay-surface-deep': mix(theme.bg1, 97),
			'--keyboard-surface': mix(theme.surface, 96), '--toast-surface': mix(theme.surface, 96),
			'--status-pop-surface': mix(theme.surface, 97), '--savebar-surface': mix(theme.bg1, 96)
		};
		for (const [key, value] of Object.entries(tokens)) root.style.setProperty(key, value);
	}
	document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme.bg);
}
