import { test, expect } from '@playwright/test';

// Uses the real backend + YouTube: search, add results to a category, render Home/Category, play a video.
test('content and playback', async ({ page, request }) => {
	test.skip(!!process.env.BT_OFFLINE, 'needs YouTube access');
	const results = await (await request.get('/api/search?q=mark%20rober%20egg%20drop&n=12')).json();
	expect(results.length).toBeGreaterThan(3);
	let cats = await (await request.get('/api/categories')).json();
	if (!cats.length) {
		await request.post('/api/categories', { data: { name: 'Science for kids', emoji: '🔬', color: '#4cc3ff', brief: 'Fun science for kids' } });
		cats = await (await request.get('/api/categories')).json();
	}
	for (const v of results.slice(0, 8)) await request.post('/api/candidates', { data: { video_id: v.id, category_id: cats[0].id } });

	await page.goto('/');
	await page.evaluate(() => localStorage.setItem('bt.profile', '1'));
	await page.goto('/');
	await page.waitForTimeout(2500);
	await page.keyboard.press('ArrowDown');
	await page.keyboard.press('ArrowRight');
	await page.waitForTimeout(800);
	await page.screenshot({ path: 'screenshots/home-rows-1920.png' });

	await page.goto(`/category/${cats[0].id}`);
	await page.waitForTimeout(2000);
	await page.screenshot({ path: 'screenshots/category-1920.png' });

	await page.goto('/search?q=mark%20rober%20egg%20drop');
	await page.waitForTimeout(3000);
	await page.screenshot({ path: 'screenshots/search-1920.png' });

	const id = results[1].id;
	await page.goto(`/watch/${id}?c=${cats[0].id}`);
	await page.waitForTimeout(1500);
	await page.screenshot({ path: 'screenshots/player-loading-1920.png' });
	await expect
		.poll(() => page.evaluate(() => (document.querySelector('video') as HTMLVideoElement)?.currentTime ?? 0), { timeout: 60_000 })
		.toBeGreaterThan(2);
	const mode = await page.evaluate(() => ((document.querySelector('video') as HTMLVideoElement).src.includes('/fallback') ? 'fallback' : 'dash'));
	console.log('playback mode', mode);
	await page.keyboard.press('ArrowRight'); // wake controls + seek
	await page.waitForTimeout(800);
	await page.screenshot({ path: 'screenshots/player-controls-1920.png' });
	await page.keyboard.press('ArrowDown');
	await page.keyboard.press('ArrowDown');
	await page.waitForTimeout(800);
	await page.screenshot({ path: 'screenshots/player-info-1920.png' });
	await page.keyboard.press('Backspace');
	await page.keyboard.press(' ');
	await page.waitForTimeout(500);
	const h = await (await request.get(`/api/history/${id}`)).json();
	expect(h.position_s).toBeGreaterThan(0);
});

// Real YouTube: hovering a thumbnail must mount a silent looping preview and tear it down on leave.
test('hover preview: silent autoplay over thumbnails, gone with the pointer', async ({ page, request }) => {
	test.skip(!!process.env.BT_OFFLINE, 'needs YouTube access');
	const results = await (await request.get('/api/search?q=mark%20rober%20egg%20drop&n=6')).json();
	expect(results.length).toBeGreaterThan(2);
	let cats = await (await request.get('/api/categories')).json();
	if (!cats.length) {
		await request.post('/api/categories', { data: { name: 'Science for kids', emoji: '🔬', color: '#4cc3ff', brief: 'Fun science for kids' } });
		cats = await (await request.get('/api/categories')).json();
	}
	for (const v of results.slice(0, 3)) await request.post('/api/candidates', { data: { video_id: v.id, category_id: cats[0].id } });

	await page.goto(`/category/${cats[0].id}`);
	await page.evaluate(() => localStorage.setItem('bt.profile', '1'));
	await page.goto(`/category/${cats[0].id}`);
	await page.waitForTimeout(1200);

	const cards = page.locator('.card');
	await expect(cards).not.toHaveCount(0);

	// hover the first card: a preview mounts and starts playing, muted
	await cards.first().hover();
	const pv = page.locator('video.bt-hover-pv');
	await pv.waitFor({ state: 'attached', timeout: 20_000 });
	await expect
		.poll(
			async () =>
				await page.evaluate(() => {
					const v = document.querySelector('video.bt-hover-pv') as HTMLVideoElement | null;
					return v ? { t: v.currentTime, muted: v.muted, paused: v.paused, err: v.error?.code ?? 0 } : null;
				}),
			{ timeout: 25_000 },
		)
		.toEqual({ t: expect.any(Number), muted: true, paused: false, err: 0 });
	await expect
		.poll(async () =>
			await page.evaluate(() => {
				const v = document.querySelector('video.bt-hover-pv') as HTMLVideoElement | null;
				return v ? v.currentTime : 0;
			}),
		)
		.toBeGreaterThan(1);

	// hovering a second card: exactly one preview, and it is the hovered video
	await cards.nth(1).hover();
	await expect.poll(async () =>
		await page.evaluate(() => document.querySelectorAll('video.bt-hover-pv').length)).toBe(1);

	// pointer leaves: the preview (and its stream) goes away
	await page.mouse.move(960, 980);
	await expect.poll(async () =>
		await page.evaluate(() => !!document.querySelector('video.bt-hover-pv')), { timeout: 3_000 }).toBe(false);
});
