// Lazy-loaded Shaka Player (DASH-only build keeps the bundle small).
type ShakaNs = typeof import('shaka-player/dist/shaka-player.dash.js').default;
let mod: Promise<ShakaNs> | null = null;

export function loadShaka(): Promise<ShakaNs> {
	if (!mod) {
		mod = import('shaka-player/dist/shaka-player.dash.js').then((m) => {
			const shaka = ((m as unknown as { default?: ShakaNs }).default ?? m) as ShakaNs;
			shaka.polyfill.installAll();
			return shaka;
		});
	}
	return mod;
}
