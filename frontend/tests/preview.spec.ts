import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

// Hover previews keep playing across feed refreshes: agent 'accept' events reload the home rows
// every few seconds in real use, and the preview under the pointer must survive them untouched.
const DATA = process.env.BT_E2E_DATA;
const BACKEND = process.env.BT_E2E_BACKEND;
const ID = 'pvhover0001'; // offline 20 s clip, seeded as an accepted candidate
const NEW_ID = 'pvhover0002'; // added mid-hover: POST /candidates -> family 'accept' -> rows reload

test.skip(!DATA || !BACKEND, 'needs scripts/e2e.sh');

test.beforeAll(() => {
	const dir = join(DATA!, 'media', ID.slice(0, 2));
	mkdirSync(dir, { recursive: true });
	execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=duration=20:size=640x360:rate=25', '-f', 'lavfi', '-i', 'sine=duration=20',
		'-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', '-movflags', '+faststart', join(dir, `${ID}.mp4`)]);
	execFileSync(join(BACKEND!, '.venv/bin/python'), ['-c', `
from sqlmodel import select
from bt.db import init_db, session
from bt.models import Candidate, Category, Download, Profile, Video, now as mnow
init_db()
with session() as s:
    pid = s.exec(select(Profile)).first().id
    s.add(Video(id="${ID}", title="Preview hover clip", channel_name="Test", duration_s=20, fetched_at=mnow()))
    s.add(Video(id="${NEW_ID}", title="Second hover video", channel_name="Test", duration_s=20, fetched_at=mnow()))
    s.merge(Download(video_id="${ID}", status="done", path="${ID.slice(0, 2)}/${ID}.mp4", size_bytes=100000, height=360, progress=1.0))
    cat = Category(profile_id=pid, name="PV hover")
    s.add(cat)
    s.commit()
    s.refresh(cat)
    s.add(Candidate(category_id=cat.id, video_id="${ID}", status="accepted", score=90))
    s.commit()
`], { cwd: BACKEND, env: { ...process.env, BT_DATA_DIR: DATA! } });
});

test('hover preview survives home reloads while hovering the same card', async ({ page, request }) => {
	page.on('console', (m) => { if (m.type() === 'error') console.log('BROWSER:', m.text().slice(0, 140)); });
	await page.route('**/api/thumb/**', (r) =>
		r.fulfill({ status: 200, contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"></svg>' }));
	await page.goto('/');
	await page.evaluate(() => localStorage.setItem('bt.profile', '1'));
	await page.goto('/');
	const card = page.locator('.card', { hasText: 'Preview hover clip' });
	await expect(card).toHaveCount(1);

	await card.hover();
	await expect
		.poll(async () => {
			return await page.evaluate(() => (document.querySelector('video.bt-hover-pv') as HTMLVideoElement | null)?.currentTime ?? 0);
		}, { timeout: 8000 })
		.toBeGreaterThan(0.8); // actually playing
	const before = await page.evaluate(() => {
		const v = document.querySelector('video.bt-hover-pv') as HTMLVideoElement;
		return { t: v.currentTime, src: v.src };
	});
	expect(before.src).toContain(`/api/video/${ID}/file`); // playing the saved copy

	// Mid-hover: a family 'accept' reloads the home rows ~1.5 s later (exactly how the AI's
	// verdicts hit a hovering user in production).
	const cats = (await (await request.get('/api/categories')).json()) as { id: number; name: string }[];
	const cat = cats.find((c) => c.name === 'PV hover');
	expect(cat).toBeTruthy();
	await request.post('/api/candidates', { data: { video_id: NEW_ID, category_id: cat!.id } });
	await page.waitForTimeout(2800); // event + reload latency + re-render

	const after = await page.evaluate(() => {
		const v = document.querySelector('video.bt-hover-pv') as HTMLVideoElement | null;
		return v ? { t: v.currentTime, src: v.src } : null;
	});
	expect(after).toBeTruthy();
	expect(after!.src).toBe(before.src); // no teardown/re-creation under the pointer
	expect(after!.t).toBeGreaterThan(before.t + 1.1); // kept playing the whole time, never restarted
});
