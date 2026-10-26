import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

mkdirSync('screenshots', { recursive: true });


// Feedback from the candidate drawer (the "verdict" detail view): a dislike removes the
// pick from the category, flips the candidate to rejected with the family's reason,
// and posts an agent event the verdict log shows.
const DATA = process.env.BT_E2E_DATA;
const BACKEND = process.env.BT_E2E_BACKEND;

test.skip(!DATA || !BACKEND, 'needs scripts/e2e.sh (seeds candidates in the throwaway data dir)');

let catId = 0;
async function getCatId(request: import('@playwright/test').APIRequestContext) {
	if (!catId) {
		const cats = await (await request.get('/api/categories')).json();
		catId = cats.find((c: { name: string }) => c.name === 'Verdict feedback test').id;
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
    cat = s.exec(select(Category).where(Category.name == "Verdict feedback test")).first()
    if not cat:
        s.add(Category(profile_id=pid, name="Verdict feedback test", brief="local LLM howtos"))
        s.commit()
        cat = s.exec(select(Category).where(Category.name == "Verdict feedback test")).one()
    s.merge(Video(id="ollama00001", title="Ollama setup for total beginners", channel_id="UCtest",
                  channel_name="Test", duration_s=600, view_count=123456))
    if not s.exec(select(Candidate).where(Candidate.category_id == cat.id,
                                         Candidate.video_id == "ollama00001")).first():
        s.add(Candidate(category_id=cat.id, video_id="ollama00001", status="accepted", score=82,
                        summary="gentle first-time walkthrough"))
    s.commit()
`], { cwd: BACKEND, env: { ...process.env, BT_DATA_DIR: DATA! } });
});

test('drawer feedback rejects the pick and records the reason for the judge', async ({ page, request }) => {
	const id = await getCatId(request);
	// other specs may have added profiles: pin ours in localStorage so the profile picker stays away
	await page.goto(`/category/${id}`);
	await page.evaluate(() => localStorage.clear());
	const profiles = await (await request.get('/api/profiles')).json();
	await page.evaluate((pid: string) => localStorage.setItem('bt.profile', pid), String(profiles[0].id));
	await page.reload();
	const card = page.locator('.cand', { hasText: 'Ollama setup for total beginners' });
	await expect(card).toBeVisible();
	await card.hover();
	await card.getByRole('button', { name: 'Why picked?' }).click();
	const drawer = page.getByRole('dialog', { name: 'Ollama setup for total beginners' });
	await expect(drawer).toBeVisible();
	await drawer.screenshot({ path: 'screenshots/verdict-drawer-1920.png' });

	// feedback dialog opens on top of the drawer
	await page.getByRole('button', { name: 'Feedback' }).click();
	const fb = page.getByRole('dialog', { name: 'Feedback on this pick' });
	await expect(fb).toBeVisible();
	await page.screenshot({ path: 'screenshots/verdict-feedback-1920.png' });
	await fb.getByRole('button', { name: 'Not for us' }).click();
	await fb.getByRole('button', { name: 'Too basic' }).click();
	await fb.getByRole('textbox').fill('too basic, want advanced ollama videos');
	await fb.getByRole('button', { name: 'Send feedback' }).click();

	await expect(page.getByText('Thanks. The AI will avoid videos like this.')).toBeVisible();
	// a dislike closes the drawer (the pick is gone from the list)
	await expect(page.getByRole('dialog')).toHaveCount(0);

	// server side: feedback stored, candidate rejected+dismissed with the family's reason
	const fbs = await (await request.get('/api/feedback')).json();
	const mine = fbs.find((f: { video_id: string }) => f.video_id === 'ollama00001');
	expect(mine?.rating).toBe(-1);
	expect(mine?.chips).toEqual(['Too basic']);
	expect(mine?.text).toBe('too basic, want advanced ollama videos');

	const evs = await (await request.get('/api/agent/events')).json();
	const ev = evs.find((e: { kind: string; message: string }) =>
		e.kind === 'reject' && e.message.includes('You rejected') && e.message.includes('Ollama'));
	expect(ev?.payload?.candidate_id).toBeTruthy();
	const detail = await (await request.get(`/api/agent/candidates/${ev.payload.candidate_id}`)).json();
	expect(detail.status).toBe('rejected');
	expect(detail.red_flags.some((f: string) => f.startsWith('Family:'))).toBe(true);

	// and the video is out of the category feed
	await page.reload();
	await expect(page.locator('.cand', { hasText: 'Ollama setup for total beginners' })).toHaveCount(0);
	const feed = await (await request.get(`/api/feed/category/${id}`)).json();
	expect(feed.some((c: { video: { id: string } }) => c.video.id === 'ollama00001')).toBe(false);
});
