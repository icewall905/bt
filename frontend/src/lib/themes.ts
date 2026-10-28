/** The first palette is the original BetterTube appearance. The other themes
 * only override visual tokens: playback, settings and profile colours are unchanged. */
export interface Theme {
	id: string; name: string; description: string;
	bg: string; bg1: string; bg2: string; surface: string; accent: string; accentInk: string;
	ai: string; text: string; muted: string; faint: string;
}

export const THEMES: Theme[] = [
	{ id: 'projector', name: 'Projector', description: 'The original violet room and warm amber.', bg: '#0a0817', bg1: '#110e26', bg2: '#1a1638', surface: '#1b1740', accent: '#ffb547', accentInk: '#1c1205', ai: '#9d86ff', text: '#f0edff', muted: '#aaa4d2', faint: '#716b9c' },
	{ id: 'ocean', name: 'Nord', description: 'Cool arctic blues and soft snow.', bg: '#242933', bg1: '#2e3440', bg2: '#3b4252', surface: '#434c5e', accent: '#88c0d0', accentInk: '#17222b', ai: '#b48ead', text: '#eceff4', muted: '#d8dee9', faint: '#b3becd' },
	{ id: 'forest', name: 'Everforest', description: 'Gentle greens and warm parchment.', bg: '#1e2326', bg1: '#272e33', bg2: '#2e383c', surface: '#374145', accent: '#a7c080', accentInk: '#1e2326', ai: '#d699b6', text: '#d3c6aa', muted: '#bec5b2', faint: '#9da9a0' },
	{ id: 'ember', name: 'Gruvbox', description: 'Earthy charcoal, cream and golden yellow.', bg: '#1d2021', bg1: '#282828', bg2: '#32302f', surface: '#3c3836', accent: '#fabd2f', accentInk: '#282828', ai: '#d3869b', text: '#ebdbb2', muted: '#d5c4a1', faint: '#bdae93' },
	{ id: 'midnight', name: 'Tokyo Night', description: 'Deep blue-violet with crisp sky blue.', bg: '#1b1e2d', bg1: '#1f2335', bg2: '#24283b', surface: '#292e42', accent: '#7aa2f7', accentInk: '#151827', ai: '#bb9af7', text: '#c0caf5', muted: '#a9b1d6', faint: '#9aa5ce' },
	{ id: 'slate', name: 'One Dark', description: 'Balanced charcoal with a mellow blue.', bg: '#181a1f', bg1: '#21252b', bg2: '#282c34', surface: '#3e4451', accent: '#61afef', accentInk: '#18212b', ai: '#c678dd', text: '#abb2bf', muted: '#abb2bf', faint: '#9da5b4' },
	{ id: 'rose', name: 'Rosé Pine', description: 'Dusky plum, rose and pale gold.', bg: '#191724', bg1: '#1f1d2e', bg2: '#26233a', surface: '#403d52', accent: '#ebbcba', accentInk: '#262033', ai: '#c4a7e7', text: '#e0def4', muted: '#c8c5dd', faint: '#aaa7c0' },
	{ id: 'aurora', name: 'Catppuccin Mocha', description: 'Soft lavender on rich midnight.', bg: '#11111b', bg1: '#181825', bg2: '#1e1e2e', surface: '#313244', accent: '#cba6f7', accentInk: '#1e1e2e', ai: '#89dceb', text: '#cdd6f4', muted: '#bac2de', faint: '#a6adc8' },
	{ id: 'copper', name: 'Solarized', description: 'Deep teal, ivory and warm yellow.', bg: '#00212b', bg1: '#002b36', bg2: '#073642', surface: '#174650', accent: '#eee8d5', accentInk: '#002b36', ai: '#2aa198', text: '#fdf6e3', muted: '#c6d1ca', faint: '#a3b6b3' },
	{ id: 'noir', name: 'Dracula', description: 'Dark graphite with violet and pink.', bg: '#191a21', bg1: '#21222c', bg2: '#282a36', surface: '#343746', accent: '#bd93f9', accentInk: '#211a2c', ai: '#8be9fd', text: '#f8f8f2', muted: '#d5d6df', faint: '#b0b4cb' },
	{ id: 'lagoon', name: 'Kanagawa', description: 'Ink blue, weathered paper and muted gold.', bg: '#16161d', bg1: '#1f1f28', bg2: '#2a2a37', surface: '#363646', accent: '#e6c384', accentInk: '#1f1f28', ai: '#7e9cd8', text: '#dcd7ba', muted: '#c8c093', faint: '#a6a69c' }
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
