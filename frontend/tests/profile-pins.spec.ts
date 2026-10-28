import { test, expect } from '@playwright/test';

test('optional profile PIN: edit, unlock, switch away, relock and remove', async ({ page, request }) => {
	await request.put('/api/settings/setup', { data: { completed: true } });
	const profiles = await (await request.get('/api/profiles')).json();
	const family = profiles[0];
	const parent = await (await request.post('/api/profiles', { data: { name: 'PIN test parent', emoji: '🦉', color: '#7c5cff' } })).json();
	await page.addInitScript(id => localStorage.setItem('bt.profile', String(id)), family.id);
	await page.goto('/settings?tab=profiles');
	const row = page.locator('.item').filter({ hasText: 'PIN test parent' });
	await row.getByRole('button', { name: 'Edit', exact: true }).click();
	await page.getByLabel('PIN (optional)').fill('4826');
	await page.getByLabel('Repeat PIN').fill('4826');
	await page.getByRole('button', { name: 'Save', exact: true }).click();
	await expect(page.getByRole('dialog', { name: /Edit/ })).toHaveCount(0);
	// A PIN is optional and does not enable the global login screen.
	expect((await (await request.get('/api/auth/status')).json()).required).toBe(false);
	await row.getByRole('button', { name: 'Switch to', exact: true }).click();
	await expect(page.getByRole('dialog', { name: 'Unlock PIN test parent' })).toBeVisible();
	await page.getByLabel('Profile PIN', { exact: true }).fill('1111');
	await page.getByRole('button', { name: 'Unlock profile', exact: true }).click();
	await expect(page.getByRole('alert')).toHaveText(/Incorrect PIN/);
	await page.getByLabel('Profile PIN', { exact: true }).fill('4826');
	await page.getByRole('button', { name: 'Unlock profile', exact: true }).click();
	await expect(row.getByText('Watching now')).toBeVisible();
	const familyRow = page.locator('.item').filter({ has: page.locator('strong', { hasText: family.name }) });
	await familyRow.getByRole('button', { name: 'Switch to', exact: true }).click();
	await expect(familyRow.getByText('Watching now')).toBeVisible();
	await row.getByRole('button', { name: 'Switch to', exact: true }).click();
	await expect(page.getByRole('dialog', { name: 'Unlock PIN test parent' })).toBeVisible();
	await page.getByRole('button', { name: 'Cancel', exact: true }).click();
	await expect(familyRow.getByText('Watching now')).toBeVisible();
	// Editing a protected profile also asks for its PIN.
	await row.getByRole('button', { name: 'Edit', exact: true }).click();
	await page.getByLabel('Profile PIN', { exact: true }).fill('4826');
	await page.getByRole('button', { name: 'Unlock profile', exact: true }).click();
	await page.getByRole('button', { name: 'Remove PIN', exact: true }).click();
	await page.getByRole('button', { name: 'Save', exact: true }).click();
	await row.getByRole('button', { name: 'Switch to', exact: true }).click();
	await expect(row.getByText('Watching now')).toBeVisible();
	await expect(page.getByRole('dialog', { name: /Unlock/ })).toHaveCount(0);
	await familyRow.getByRole('button', { name: 'Switch to', exact: true }).click();
	await request.delete(`/api/profiles/${parent.id}`);
});

test('a locked saved profile stays behind the picker after reload', async ({ page, request }) => {
	await request.put('/api/settings/setup', { data: { completed: true } });
	const parent = await (await request.post('/api/profiles', { data: { name: 'Reload PIN parent', pin: '8426' } })).json();
	await page.goto('/settings');
	await page.evaluate(id => localStorage.setItem('bt.profile', String(id)), parent.id);
	await page.reload();
	await expect(page.getByRole('heading', { name: "Who's watching?" })).toBeVisible();
	await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toHaveCount(0);
	await page.getByRole('button', { name: /Reload PIN parent/ }).click();
	await page.getByLabel('Profile PIN', { exact: true }).fill('8426');
	await page.getByRole('button', { name: 'Unlock profile', exact: true }).click();
	await expect(page.getByRole('heading', { name: "Who's watching?" })).toHaveCount(0);
	await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Switch profile' }).click();
	await page.getByRole('button', { name: 'Lock profile', exact: true }).click();
	await expect(page.getByRole('heading', { name: "Who's watching?" })).toBeVisible();
	await page.screenshot({ path: 'screenshots/profile-pin-picker.png' });
	const profiles = await (await request.get('/api/profiles')).json();
	const other = profiles.find((p: { id: number }) => p.id !== parent.id);
	await page.getByRole('button', { name: new RegExp(other.name) }).click();
	await request.post(`/api/profiles/${parent.id}/unlock`, { data: { pin: '8426' } });
	await request.delete(`/api/profiles/${parent.id}`);
});
