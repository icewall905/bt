/** The first palette is the original BetterTube appearance. The other themes
 * only override visual tokens: playback, settings and profile colours are unchanged. */
export interface Theme {
	id: string; name: string; description: string;
	bg: string; bg1: string; bg2: string; surface: string; accent: string; accentInk: string;
	ai: string; text: string; muted: string; faint: string;
}

export const THEMES: Theme[] = [
	{ id: 'projector', name: 'Projector', description: 'The original violet room and warm amber.', bg: '#0a0817', bg1: '#110e26', bg2: '#1a1638', surface: '#1b1740', accent: '#ffb547', accentInk: '#1c1205', ai: '#9d86ff', text: '#f0edff', muted: '#aaa4d2', faint: '#716b9c' },
	{ id: 'ocean', name: 'Deep Ocean', description: 'Inky blue water and bright sea glass.', bg: '#05131d', bg1: '#0a2132', bg2: '#10364a', surface: '#113449', accent: '#76dcf4', accentInk: '#06202a', ai: '#70b7ff', text: '#e8f8ff', muted: '#afcbd8', faint: '#89aab9' },
	{ id: 'forest', name: 'Forest', description: 'Deep evergreen with fresh mint.', bg: '#07150f', bg1: '#0d241b', bg2: '#153a2b', surface: '#183d2d', accent: '#8ce2a9', accentInk: '#0b2415', ai: '#8bd2bc', text: '#e9fff1', muted: '#b3d1bc', faint: '#8bac96' },
	{ id: 'ember', name: 'Ember', description: 'Warm charcoal, firelight and terracotta.', bg: '#1b0c09', bg1: '#2c1712', bg2: '#43231a', surface: '#46271e', accent: '#ffaf75', accentInk: '#321309', ai: '#f19c7d', text: '#fff0e8', muted: '#dfb9aa', faint: '#be9485' },
	{ id: 'midnight', name: 'Midnight', description: 'Navy skies with a cool blue accent.', bg: '#080d1e', bg1: '#101a35', bg2: '#1b2b50', surface: '#1d3157', accent: '#9ec5ff', accentInk: '#0b1b35', ai: '#95a7ff', text: '#eef4ff', muted: '#b5c4df', faint: '#8f9fbc' },
	{ id: 'slate', name: 'Slate', description: 'Quiet graphite and soft ice blue.', bg: '#0d1217', bg1: '#18212a', bg2: '#253440', surface: '#263844', accent: '#a1d8ee', accentInk: '#10212a', ai: '#a0bedb', text: '#eff8fb', muted: '#bbccd3', faint: '#94aab4' },
	{ id: 'rose', name: 'Rosewood', description: 'Dark plum with a gentle rose glow.', bg: '#1a0b17', bg1: '#2d1527', bg2: '#44243b', surface: '#49283f', accent: '#ffb1cf', accentInk: '#310d20', ai: '#e2a6ee', text: '#fff0f8', muted: '#ddbad0', faint: '#bc97af' },
	{ id: 'aurora', name: 'Aurora', description: 'Night skies lit by violet and teal.', bg: '#07151a', bg1: '#10252d', bg2: '#193743', surface: '#1b3a43', accent: '#92efd1', accentInk: '#06261c', ai: '#b2a2ff', text: '#ebfffa', muted: '#b0d2ca', faint: '#8bacaa' },
	{ id: 'copper', name: 'Copper', description: 'Earthy brown, brass and warm cream.', bg: '#18110a', bg1: '#2a2013', bg2: '#3e301c', surface: '#413321', accent: '#f6c674', accentInk: '#2b1c08', ai: '#dab78e', text: '#fff5e5', muted: '#ddc9a9', faint: '#b9a587' },
	{ id: 'noir', name: 'Noir', description: 'Near-black, silver and clean white.', bg: '#090a0d', bg1: '#14161c', bg2: '#22252d', surface: '#272b35', accent: '#e2e8f2', accentInk: '#151922', ai: '#b4c1d6', text: '#f5f7fb', muted: '#c0c6d2', faint: '#9aa4b3' },
	{ id: 'lagoon', name: 'Lagoon', description: 'Petrol blue with vivid coral.', bg: '#071519', bg1: '#10272b', bg2: '#193d3e', surface: '#1b4040', accent: '#ffb198', accentInk: '#31170f', ai: '#79daca', text: '#ecfffb', muted: '#b2d2cc', faint: '#8aaca7' }
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
			'--line': mix(theme.text, 15), '--line-strong': mix(theme.text, 30),
			'--text': theme.text, '--muted': theme.muted, '--faint': theme.faint,
			'--accent': theme.accent, '--accent-2': mix(theme.accent, 75, 'white'), '--accent-ink': theme.accentInk,
			'--accent-glow': mix(theme.accent, 48), '--ai': theme.ai,
			'--ambient-1': mix(theme.ai, 20), '--ambient-2': mix(theme.accent, 7), '--ambient-3': mix(theme.ai, 15),
			'--modal-top': mix(theme.surface, 95), '--modal-bottom': mix(theme.bg1, 97),
			'--overlay-surface': mix(theme.surface, 96), '--overlay-surface-deep': mix(theme.bg1, 97),
			'--keyboard-surface': mix(theme.surface, 96), '--toast-surface': mix(theme.surface, 96),
			'--status-pop-surface': mix(theme.surface, 97), '--savebar-surface': mix(theme.bg1, 96)
		};
		for (const [key, value] of Object.entries(tokens)) root.style.setProperty(key, value);
	}
	document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme.bg);
}
