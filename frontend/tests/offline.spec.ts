import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { freshPage } from './helpers';

// Offline cache (Ticket D): a finished download plays from /api/video/{id}/file, no Shaka/YouTube.
const DATA = process.env.BT_E2E_DATA;
const BACKEND = process.env.BT_E2E_BACKEND;
const ID = 'offlinetst1';

test.skip(!DATA || !BACKEND, 'needs scripts/e2e.sh (seeds a fake download in the throwaway data dir)');

test.beforeAll(() => {
	const dir = join(DATA!, 'media', ID.slice(0, 2));
	mkdirSync(dir, { recursive: true });
	execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=duration=20:size=640x360:rate=25', '-f', 'lavfi', '-i', 'sine=duration=20',
		'-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', '-movflags', '+faststart', join(dir, `${ID}.mp4`)]);
	execFileSync(join(BACKEND!, '.venv/bin/python'), ['-c', `
from bt.db import init_db, session
from bt.models import Download, Video
init_db()
with session() as s:
    s.merge(Video(id="${ID}", title="Offline test clip", channel_name="Test"))
    s.merge(Download(video_id="${ID}", status="done", path="${ID.slice(0, 2)}/${ID}.mp4", size_bytes=100000, height=360, progress=1.0))
    s.commit()
`], { cwd: BACKEND, env: { ...process.env, BT_DATA_DIR: DATA! } });
});

for (const known of [true, false]) {
	test(`plays the saved copy (${known ? 'detail says done' : 'detail unavailable, probes file'})`, async ({ page }) => {
		const manifest: string[] = [];
		page.on('request', (r) => r.url().includes('manifest.mpd') && manifest.push(r.url()));
		await page.route(new RegExp(`/api/video/${ID}$`), (r) =>
			known
				? r.fulfill({ json: { id: ID, title: 'Offline test clip', channel_name: 'Test', channel_id: '', duration_s: 20, view_count: 0, like_count: 0, published_at: null, thumbnail: '', is_short: false, is_live: false, download: { status: 'done', progress: 1, height: 360, size_bytes: 100000, pinned: true }, history: { position_s: 0, finished: false }, in_categories: [] } })
				: r.fulfill({ status: 503, json: { detail: 'YouTube blocked the request' } })
		);
		await freshPage(page, '/');
		await page.goto(`/watch/${ID}`);
		await expect.poll(() => page.evaluate(() => (document.querySelector('video') as HTMLVideoElement)?.currentTime ?? 0), { timeout: 20000 }).toBeGreaterThan(1);
		expect(await page.evaluate(() => (document.querySelector('video') as HTMLVideoElement).src)).toContain(`/api/video/${ID}/file`);
		expect(manifest).toEqual([]);
		await expect(page.getByRole('heading', { name: "Can't play this video" })).toHaveCount(0);
		await page.keyboard.press('ArrowRight');
		await expect(page.getByRole('button', { name: 'Quality' })).toContainText('Offline 360p');
	});
}

test('storage tab lists the saved video', async ({ page }) => {
	await freshPage(page, '/settings?tab=storage');
	await expect(page.getByText('Offline test clip')).toBeVisible();
	await page.screenshot({ path: 'screenshots/settings-storage-1920.png' });
});
