import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { freshPage } from './helpers';

// The Agent page must never scroll sideways, even with very long log messages and titles
// (implicit grid tracks used to size to the no-wrap max-content and blow past the viewport).
const DATA = process.env.BT_E2E_DATA;
const BACKEND = process.env.BT_E2E_BACKEND;

test.skip(!DATA || !BACKEND, 'needs scripts/e2e.sh (seeds long agent events in the throwaway data dir)');

const LONG = 'A '.repeat(120) + 'very long single-line event message that must ellipsize instead of widening the page';

test.beforeAll(() => {
	execFileSync(join(BACKEND!, '.venv/bin/python'), ['-c', `
from sqlmodel import select
from bt.db import init_db, session
from bt.models import AgentEvent, Category, Profile
init_db()
with session() as s:
    if not s.exec(select(Profile)).first():
        s.add(Profile(name="Family"))
    s.commit()
    pid = s.exec(select(Profile)).first().id
    s.add(Category(profile_id=pid, name="A category with a quite long name so the queue header row is wide", brief="b"))
    s.commit()
    cid = s.exec(select(Category)).first().id
    for kind in ("plan", "search", "judge", "reject", "learn"):
        s.add(AgentEvent(kind=kind, level="info", message="${LONG}", category_id=cid, profile_id=pid))
    s.commit()
`], { cwd: BACKEND, env: { ...process.env, BT_DATA_DIR: DATA! } });
});

for (const [w, h] of [[1920, 1080], [1280, 720], [854, 480]] as [number, number][]) {
	test(`fits the viewport at ${w}x${h}`, async ({ page }) => {
		await page.setViewportSize({ width: w, height: h });
		await freshPage(page, '/agent');
		await expect(page.getByRole('heading', { name: 'Live log' })).toBeVisible();
		await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth), { timeout: 5000 })
			.toBeLessThanOrEqual(w);
	});
}
