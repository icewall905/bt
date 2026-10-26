import { expect, test } from '@playwright/test';
import { freshPage, resetBackend } from './helpers';

// The proxy helper in Settings → AI → Pace and limits: pick a provider, fill fields,
// test the composed URL before saving, then save and confirm it is stored masked.

test.beforeAll(async ({ request }) => {
	await resetBackend(request);
});

test.afterAll(async ({ request }) => {
	await request.put('/api/settings/throttle', { data: { proxy: '' } });
});

test('proxy helper composes a URL and reports an unreachable proxy', async ({ page }) => {
	await freshPage(page, '/settings?tab=ai');

	// Direct by default: no test possible, no dirty flag from the proxy section.
	await expect(page.getByRole('button', { name: 'Test this proxy' })).toBeDisabled();

	// Local VPN helper: host + port compose an http URL.
	await page.getByRole('button', { name: 'Local VPN' }).click();
	await page.getByLabel('Host').fill('127.0.0.1');
	await page.getByLabel('Port').fill('9');
	await page.getByRole('button', { name: 'Test this proxy' }).click();
	await expect(page.getByText('Could not use this proxy')).toBeVisible();
	await expect(page.getByText('Could not reach the proxy', { exact: false })).toBeVisible();

	// PIA helper: credentials + region compose the socks5 URL and save masked.
	await page.getByRole('button', { name: 'PIA', exact: true }).click();
	await page.getByLabel('SOCKS5 username').fill('u1234567890');
	await page.getByLabel('SOCKS5 password').fill('secret');
	await expect(page.getByRole('button', { name: 'Test this proxy' })).toBeEnabled();
	await page.locator('section', { hasText: 'Pace and limits' }).getByRole('button', { name: 'Save changes' }).click();
	await expect(page.getByText('Limits saved')).toBeVisible();

	const st = await (await page.request.get('/api/settings')).json();
	expect(st.throttle.proxy).toBe('********');
});
