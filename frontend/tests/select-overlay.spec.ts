import { test, expect } from '@playwright/test';

for (const viewport of [{ width: 1360, height: 768 }, { width: 390, height: 640 }]) {
	test(`provider menu covers the screen and scrolls at ${viewport.width}px`, async ({ page }) => {
		await page.setViewportSize(viewport);
		await page.goto('/settings?tab=ai');
		const provider = page.getByRole('button', { name: /^Provider/ });
		await provider.scrollIntoViewIfNeeded();
		await provider.click();
		const dialog = page.getByRole('dialog', { name: 'Provider' });
		await expect(dialog).toBeVisible();
		const metrics = await dialog.evaluate(el => {
			const overlay = el.parentElement!;
			const bounds = overlay.getBoundingClientRect();
			const box = el.getBoundingClientRect();
			const corner = document.elementFromPoint(5, innerHeight - 5);
			return {
				parentIsBody: overlay.parentElement === document.body,
				bounds: { x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height },
				dialog: { top: box.top, bottom: box.bottom },
				cornerCovered: corner === overlay || overlay.contains(corner)
			};
		});
		expect(metrics.parentIsBody).toBe(true);
		expect(metrics.bounds).toEqual({ x: 0, y: 0, width: viewport.width, height: viewport.height });
		expect(metrics.dialog.top).toBeGreaterThanOrEqual(0);
		expect(metrics.dialog.bottom).toBeLessThanOrEqual(viewport.height);
		expect(metrics.cornerCovered).toBe(true);
		// A provider near the bottom must remain reachable despite the longer list.
		const last = dialog.getByRole('option', { name: /^Mistral/ });
		await last.scrollIntoViewIfNeeded();
		await expect(last).toBeInViewport();
		await page.screenshot({ path: `screenshots/provider-overlay-${viewport.width}.png` });
		await last.click();
		await expect(dialog).toHaveCount(0);
		await expect(provider).toContainText('Mistral');
		await provider.click();
		await page.keyboard.press('Escape');
		await expect(dialog).toHaveCount(0);
		await provider.click();
		await page.mouse.click(5, 5);
		await expect(dialog).toHaveCount(0);
	});
}
