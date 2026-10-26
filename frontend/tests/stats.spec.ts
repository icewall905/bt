import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

// The Statistics page: overview tiles, per-category table, daily activity table.
const DATA = process.env.BT_E2E_DATA;
const BACKEND = process.env.BT_E2E_BACKEND;

test.skip(!DATA || !BACKEND, 'needs scripts/e2e.sh (seeds candidates in the throwaway data dir)');

test.beforeAll(() => {
	execFileSync(join(BACKEND!, '.venv/bin/python'), ['-c', `
from sqlmodel import select
from bt.db import init_db, session
from bt.models import Candidate, Category, Profile, Video, WatchHistory, now
init_db()
with session() as s:
    if not s.exec(select(Profile)).first():
        s.add(Profile(name="Family"))
    s.commit()
    pid = s.exec(select(Profile)).first().id
    cat = s.exec(select(Category).where(Category.name == "Stats test")).first()
    if not cat:
        s.add(Category(profile_id=pid, name="Stats test", brief="b"))
        s.commit()
        cat = s.exec(select(Category).where(Category.name == "Stats test")).one()
    for vid, title in [("statvid00001", "Watched on the stats test list"), ("statvid00002", "Still queued")]:
        s.merge(Video(id=vid, title=title, channel_id="UCtest", channel_name="Test", duration_s=600))
        if not s.exec(select(Candidate).where(Candidate.category_id == cat.id,
                                             Candidate.video_id == vid)).first():
            s.add(Candidate(category_id=cat.id, video_id=vid, status="accepted", score=75, judged_at=now()))
    if not s.exec(select(WatchHistory).where(WatchHistory.video_id == "statvid00001")).first():
        s.add(WatchHistory(profile_id=pid, video_id="statvid00001", category_id=cat.id,
                           finished=True, duration_s=600, position_s=600))
    s.commit()
`], { cwd: BACKEND, env: { ...process.env, BT_DATA_DIR: DATA! } });
});

test('stats page shows queue, category and daily numbers', async ({ page, request }) => {
	await page.goto('/stats');
	await page.evaluate(() => localStorage.clear());
	const profiles = await (await request.get('/api/profiles')).json();
	await page.evaluate((pid: string) => localStorage.setItem('bt.profile', pid), String(profiles[0].id));
	await page.reload();

	await expect(page.getByRole('heading', { name: 'Statistics' })).toBeVisible();
	// overview tiles render real numbers, not skeletons
	await expect(page.getByText('Ready in queues')).toBeVisible();
	await expect(page.getByText('Waiting to be judged')).toBeVisible();

	// per-category row: one watched, one still queued
	const row = page.locator('tr', { hasText: 'Stats test' });
	await expect(row).toBeVisible();
	await expect(row.locator('td').nth(3)).toHaveText('1');
	await expect(row.getByText('Still queued')).toHaveCount(0); // titles never leak into the counts table
	const ready = await row.locator('td').nth(1).innerText();
	expect(ready).toMatch(/1\/20/); // in_queue/target with gauge

	// today's row in the daily table counts the watch (rows are newest first)
	const dailySection = page.locator('section.panel', { hasText: 'Daily activity' });
	const today = dailySection.locator('tbody tr').first();
	await expect(today).toBeVisible();
	await expect(today.locator('td').nth(2)).toContainText('1');
	// the per-category breakdown shows which list it was watched on
	expect(await today.locator('td').nth(2).innerText()).toMatch(/✨ ×1/);

	// range chips re-fetch without breaking
	await page.getByRole('button', { name: '7 days' }).click();
	await expect(page.getByRole('heading', { name: 'Daily activity' })).toContainText('last 7 days');
	const r = await (await request.get('/api/stats/page?days=7')).json();
	expect(r.daily).toHaveLength(7);
	const cat = r.categories.find((c: { name: string }) => c.name === 'Stats test');
	expect(cat.counts.watched).toBe(1);
	expect(cat.counts.in_queue).toBe(1);
});
