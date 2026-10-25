import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { freshPage } from './helpers';

// "Seen it" on a category card: the video disappears from the feed and is marked watched.
const DATA = process.env.BT_E2E_DATA;
const BACKEND = process.env.BT_E2E_BACKEND;

test.skip(!DATA || !BACKEND, 'needs scripts/e2e.sh (seeds candidates in the throwaway data dir)');

let catId = 0;
async function getCatId(request: import('@playwright/test').APIRequestContext) {
	if (!catId) {
		const cats = await (await request.get('/api/categories')).json();
		catId = cats.find((c: { name: string }) => c.name === 'Seen it test').id;
	}
	return catId;
}

test.beforeAll(() => {
	execFileSync(join(BACKEND!, '.venv/bin/python'), ['-c', `
from sqlmodel import select
from bt.db import init_db, session
from bt.models import Candidate, Category, Profile, Video
init_db()
with session() as s:
    if not s.exec(select(Profile)).first():
        s.add(Profile(name="Family"))
    s.commit()
    pid = s.exec(select(Profile)).first().id
    cat = s.exec(select(Category).where(Category.name == "Seen it test")).first()
    if not cat:
        s.add(Category(profile_id=pid, name="Seen it test", brief="b"))
        s.commit()
        cat = s.exec(select(Category).where(Category.name == "Seen it test")).one()
    for vid, title, ch in [("seenit00000", "Video the family has seen", "UCtest"),
                          ("other000000", "Video still fresh", "UCtest"),
                          ("badch000001", "Video from a disliked channel", "UCbad")]:
        s.merge(Video(id=vid, title=title, channel_id=ch,
                      channel_name="Test" if ch == "UCtest" else "Disliked", duration_s=600))
        if not s.exec(select(Candidate).where(Candidate.category_id == cat.id,
                                             Candidate.video_id == vid)).first():
            s.add(Candidate(category_id=cat.id, video_id=vid, status="accepted", score=80, summary="x"))
    s.commit()
`], { cwd: BACKEND, env: { ...process.env, BT_DATA_DIR: DATA! } });
});

test('Seen it removes the card and keeps the rest', async ({ page, request }) => {
	const id = await getCatId(request);
	await freshPage(page, `/category/${id}`);
	await expect(page.getByRole('heading', { name: 'Seen it test' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Video the family has seen' })).toBeVisible();

	await page.locator('.cand', { hasText: 'Video the family has seen' })
		.getByRole('button', { name: 'Seen it' }).click();

	await expect(page.getByRole('link', { name: 'Video the family has seen' })).toHaveCount(0);
	await expect(page.getByRole('link', { name: 'Video still fresh' })).toBeVisible();
	await expect(page.getByText("Marked as seen. The AI won't suggest it again.")).toBeVisible();

	// server side: gone from the feed, watched in history
	const feed = await (await request.get(`/api/feed/category/${id}`)).json();
	expect(feed.map((c: { video: { id: string } }) => c.video.id)).not.toContain('seenit00000');
	expect(feed.map((c: { video: { id: string } }) => c.video.id)).toContain('other000000');
	const hist = await (await request.get('/api/history/seenit00000')).json();
	expect(hist.finished).toBe(true);
});

test("Don't like channel clears its cards and blocks it", async ({ page, request }) => {
	const id = await getCatId(request);
	await freshPage(page, `/category/${id}`);
	await expect(page.getByRole('link', { name: 'Video from a disliked channel' })).toBeVisible();

	await page.locator('.cand', { hasText: 'Video from a disliked channel' })
		.getByRole('button', { name: "Don't like channel" }).click();

	await expect(page.getByRole('link', { name: 'Video from a disliked channel' })).toHaveCount(0);
	await expect(page.getByText('No more from Disliked. The AI will skip that channel.')).toBeVisible();
	// the other channel's cards are untouched (only cards not yet marked seen in test 1)
	await expect(page.getByRole('link', { name: 'Video still fresh' })).toBeVisible();

	const feed = await (await request.get(`/api/feed/category/${id}`)).json();
	expect(feed.some((c: { video: { id: string } }) => c.video.id === 'badch000001')).toBe(false);
	const chans = await (await request.get('/api/channels')).json();
	expect(chans.find((c: { id: string }) => c.id === 'UCbad')?.blocked).toBe(true);
});
