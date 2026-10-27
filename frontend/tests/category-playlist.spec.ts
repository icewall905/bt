import { expect, test } from '@playwright/test';
import { freshPage, resetBackend } from './helpers';

test.beforeAll(async ({ request }) => { await resetBackend(request); });

test('new category can start from a playlist without a written brief', async ({ page }) => {
    let submitted = false;
    await page.route('**/api/categories', async route => {
        if (route.request().method() !== 'POST') return route.continue();
        const body = route.request().postDataJSON();
        expect(body.name).toBe('Playlist science');
        expect(body.playlist_url).toBe('https://www.youtube.com/playlist?list=PLscience');
        expect(body.brief).toBe('');
        expect(body.target_queue).toBe(20);
        submitted = true;
        await route.fulfill({ json: { ...body, id: 900, profile_id: 1, brief: 'Generated science prompt' } });
    });
    await freshPage(page, '/settings?tab=categories&new=1');
    await page.getByLabel('Name', { exact: true }).fill('Playlist science');
    await page.getByLabel('Initial playlist URL (optional)').fill('https://www.youtube.com/playlist?list=PLscience');
    await expect(page.getByText('Optional extra preferences to add to the generated prompt.')).toBeVisible();
    await page.getByRole('button', { name: 'Create playlist', exact: true }).click();
    await expect.poll(() => submitted).toBe(true);
    await expect(page).toHaveURL(/tab=categories$/);
});
