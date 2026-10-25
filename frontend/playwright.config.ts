import { defineConfig } from '@playwright/test';

// Runs against a backend that already serves frontend/build. `npm run test:e2e` starts one with a fresh
// data dir (scripts/e2e.sh). tests/content.spec.ts talks to real YouTube and only runs with BT_LIVE=1.
export default defineConfig({
	testDir: 'tests',
	testIgnore: process.env.BT_LIVE ? [] : ['**/content.spec.ts'],
	timeout: 120_000,
	expect: { timeout: 10_000 },
	workers: 1,
	reporter: [['list']],
	use: {
		baseURL: process.env.BT_URL ?? 'http://localhost:6699',
		channel: process.env.PW_CHANNEL ?? 'chrome',
		viewport: { width: 1920, height: 1080 },
		reducedMotion: 'reduce',
		// Same as the projector kiosk (host/bt-mode).
		launchOptions: { args: ['--autoplay-policy=no-user-gesture-required'] }
	}
});
