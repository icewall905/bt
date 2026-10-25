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
