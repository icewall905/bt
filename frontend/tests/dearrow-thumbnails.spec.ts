import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { resetBackend } from './helpers';

test('the thumbnail setting changes browsing images and survives a reload', async ({ page, request }) => {
	await resetBackend(request);
	const backend = process.env.BT_E2E_BACKEND!;
	const data = process.env.BT_E2E_DATA!;
	execFileSync(join(backend, '.venv/bin/python'), ['-c', `
from bt.db import session
from bt.models import Category, Candidate, Profile, Video
from sqlmodel import select
with session() as s:
    profile = s.exec(select(Profile).order_by(Profile.id)).first()
    category = Category(profile_id=profile.id, name="Thumbnail test")
    s.add(category); s.commit(); s.refresh(category)
    s.add(Video(id="thumbtest01", title="A test thumbnail", duration_s=600))
    s.add(Candidate(category_id=category.id, video_id="thumbtest01", status="accepted", score=90))
    s.commit()
`], { cwd: backend, env: { ...process.env, BT_DATA_DIR: data } });
	await page.route('**/api/thumb/**', route => route.fulfill({
		status: 200, contentType: 'image/png',
		body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+kYz8AAAAASUVORK5CYII=', 'base64')
	}));
	await page.goto('/settings?tab=extras');
	const toggle = page.getByRole('switch', { name: /Better thumbnails \(DeArrow\)/ });
	await expect(toggle).toHaveAttribute('aria-checked', 'false');
	await toggle.click();
	await page.getByRole('button', { name: 'Save changes' }).click();
	await expect(toggle).toHaveAttribute('aria-checked', 'true');
	await expect.poll(async () => (await (await request.get('/api/settings')).json()).extras.dearrow_thumbnails).toBe(true);
	await page.goto('/');
	const image = page.locator('.card').filter({ has: page.locator('a[href^="/watch/thumbtest01"]') }).locator('img');
	await expect(image).toHaveAttribute('src', /dearrow=1/);
	await page.reload();
	await expect(image).toHaveAttribute('src', /dearrow=1/);
	await page.goto('/settings?tab=extras');
	await expect(toggle).toHaveAttribute('aria-checked', 'true');
	await toggle.click();
	await page.getByRole('button', { name: 'Save changes' }).click();
	await page.goto('/');
	await expect(image).not.toHaveAttribute('src', /dearrow=1/);
});
