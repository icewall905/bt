import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { freshPage, resetBackend } from './helpers';

// Clicking a category wherever it is listed (Home rows, Stats, …) opens that category's view.
const DATA = process.env.BT_E2E_DATA;
const BACKEND = process.env.BT_E2E_BACKEND;
test.skip(!DATA || !BACKEND, 'needs scripts/e2e.sh');

/** Home rows only list accepted candidates; there is no API to accept one, so seed it directly. */
function seedAccepted(catId: number, videoId: string, title: string) {
	execFileSync(join(BACKEND!, '.venv/bin/python'), ['-c', `
from sqlmodel import select
from bt.db import init_db, session
from bt.models import Candidate, Video
init_db()
with session() as s:
    s.merge(Video(id="${videoId}", title="${title}", channel_id="UCtest",
                  channel_name="Test", duration_s=600, view_count=123))
    if not s.exec(select(Candidate).where(Candidate.video_id == "${videoId}")).first():
        s.add(Candidate(category_id=${catId}, video_id="${videoId}", status="accepted", score=80, summary="x"))
    s.commit()
`], { cwd: BACKEND, env: { ...process.env, BT_DATA_DIR: DATA! } });
}

test('home: clicking a category row title opens the category view', async ({ page, request }) => {
	await resetBackend(request);
	const cat = await (await request.post('/api/categories', { data: { name: 'Title link test', brief: 'b' } })).json();
	seedAccepted(cat.id, 'titlelink00', 'Video behind the title link');

	await freshPage(page, '/');
	const title = page.locator('.row h2 a[href="/category/' + cat.id + '"]');
	await expect(title).toHaveText(/Title link test/);
	await expect(page.locator('.row h2 a')).toHaveCount(1); // non-category rows keep plain titles
	await title.click();

	await expect(page).toHaveURL('/category/' + cat.id);
	await expect(page.getByRole('heading', { name: 'Title link test' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Video behind the title link' })).toBeVisible();
});

test('stats: clicking a category opens that category', async ({ page, request }) => {
	await resetBackend(request);
	const cat = await (await request.post('/api/categories', { data: { name: 'Stats link test', brief: 'b' } })).json();
	seedAccepted(cat.id, 'statslink00', 'Video found via stats');

	await freshPage(page, '/stats');
	const link = page.locator('a.cat[href="/category/' + cat.id + '"]');
	await expect(link).toContainText('Stats link test');
	await link.click();

	await expect(page).toHaveURL('/category/' + cat.id);
	await expect(page.getByRole('heading', { name: 'Stats link test' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Video found via stats' })).toBeVisible();
});

test('stats: clicking another profile\'s category switches to its profile first', async ({ page, request }) => {
	await resetBackend(request);
	const other = await (await request.post('/api/profiles', { data: { name: 'Second' } })).json();
	const headers = { 'X-Profile-Id': String(other.id) };
	const cat = await (await request.post('/api/categories', { data: { name: 'Foreign category', brief: 'b' }, headers })).json();
	seedAccepted(cat.id, 'foreignlink0', 'Video from the other profile');

	await freshPage(page, '/stats');
	const link = page.locator('a.cat[href="/category/' + cat.id + '"]');
	await expect(link).toContainText('Foreign category');
	// Two profiles and no remembered choice → the app asks "Who's watching?". Pick the default
	// so stats is browsed as it; the category click must then switch to the other profile.
	const picker = page.getByRole('dialog', { name: "Who's watching?" });
	if (await picker.isVisible()) await picker.locator('button.person').first().click();
	await link.click();

	await expect(page).toHaveURL('/category/' + cat.id);
	await expect(page.getByRole('heading', { name: 'Foreign category' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Video from the other profile' })).toBeVisible();
	await expect.poll(() => page.evaluate(() => localStorage.getItem('bt.profile'))).toBe(String(other.id));
});

test('settings and category view show the category age', async ({ page, request }) => {
	await resetBackend(request);
	const cat = await (await request.post('/api/categories', { data: { name: 'Age display test', brief: 'b' } })).json();
	// Pin created_at 40 days back so the age reads "1 mo ago" however long the run takes.
	execFileSync(join(BACKEND!, '.venv/bin/python'), ['-c', `
from datetime import datetime, timedelta, timezone
from bt.db import init_db, session
from bt.models import Category
init_db()
with session() as s:
	c = s.get(Category, ${cat.id})
	c.created_at = datetime.now(timezone.utc) - timedelta(days=40)
	s.add(c)
	s.commit()
`], { cwd: BACKEND, env: { ...process.env, BT_DATA_DIR: DATA! } });

	await freshPage(page, '/settings?tab=categories');
	await expect(page.getByRole('heading', { name: 'Playlists', exact: true })).toBeVisible();
	await expect(page.locator('.item', { hasText: 'Age display test' })).toContainText('created 1 mo ago');
	await freshPage(page, '/settings?tab=playlists&new=1');
	await expect(page.getByRole('heading', { name: 'New playlist', exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Create playlist', exact: true })).toBeVisible();

	await freshPage(page, '/category/' + cat.id);
	await expect(page.locator('.head')).toContainText('Created 1 mo ago');
	await expect(page.getByRole('link', { name: 'Edit playlist', exact: true })).toBeVisible();
});
