import { expect, test } from '@playwright/test';
import { freshPage, resetBackend } from './helpers';

// Settings → Cookies: the green dot only means a file exists; the Check cookies button
// verifies the session against YouTube (anonymous history = not signed in).

test.beforeAll(async ({ request }) => {
	await resetBackend(request);
});

test.afterAll(async ({ request }) => {
	await request.delete('/api/cookies');
});

test('cookies tab validates the uploaded session', async ({ page }) => {
	await freshPage(page, '/settings?tab=cookies');

	// Nothing installed: no check button yet.
	await expect(page.getByText('No cookies installed')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Check cookies' })).toHaveCount(0);

	// Upload a dummy cookies.txt (shape-checked server-side only).
	await page.getByLabel('…or paste the file contents').fill(
		'# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1234567890\tVISITOR_INFO1_LIVE\tDummy\t0'
	);
	await page.getByRole('button', { name: 'Install cookies' }).click();
	await expect(page.getByText('Cookies are installed')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Check cookies' })).toBeVisible();

	// The check runs automatically after upload and reports a verdict.
	const result = page.locator('.result');
	await expect(result).toBeVisible({ timeout: 90_000 });
	await expect(result).toContainText('✕');

	// The import section appears with cookies installed, with both actions reachable.
	await expect(page.getByRole('heading', { name: 'Import from your YouTube account' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Import subscriptions' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Import into category' })).toBeVisible();
	await expect(page.locator('button.select').filter({ hasText: 'Into category' })).toBeVisible();
});
