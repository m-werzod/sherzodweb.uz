import { test, expect, type Page } from '@playwright/test';

/**
 * Public-surface smoke. Every assertion here was validated by hand against
 * production during the mobile-responsive audit, so the suite is green on a
 * healthy deploy and only goes red on a real regression (broken page, layout
 * overflow on phones). The `mobile` project runs every test at iPhone 13
 * width (390px); the no-overflow guard is the mobile-regression tripwire.
 */

/** No element may push the page wider than the viewport (horizontal scroll). */
async function expectNoOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const el = document.scrollingElement;
    return el ? el.scrollWidth - el.clientWidth : 0;
  });
  expect(overflow, 'horizontal overflow (px)').toBeLessThanOrEqual(2);
}

test.describe('public surface', () => {
  test('landing renders hero + brand', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('/');
    await expect(page.locator('h1').first()).toBeVisible();
    await expect(page.getByText(/SMM Coach/i).first()).toBeVisible();
    await expectNoOverflow(page);
    expect(errors, 'uncaught page errors').toEqual([]);
  });

  test('sign-in page renders a form', async ({ page }) => {
    await page.goto('/sign-in');
    await expect(page.locator('input').first()).toBeVisible();
    await expectNoOverflow(page);
  });

  test('sign-up chat boots', async ({ page }) => {
    await page.goto('/sign-up');
    // The signup chat streams its first bot bubble client-side, then shows the
    // name input. Waiting for any visible input proves the wizard mounted.
    await expect(page.locator('input, textarea').first()).toBeVisible({ timeout: 20_000 });
    await expectNoOverflow(page);
  });

  for (const path of ['/pricing', '/privacy', '/terms']) {
    test(`marketing ${path} responds 2xx/3xx`, async ({ page }) => {
      const res = await page.goto(path);
      expect(res?.status() ?? 0, `${path} status`).toBeLessThan(400);
      await expect(page.locator('body')).toBeVisible();
    });
  }
});

test.describe('auth guard', () => {
  test('unauthenticated /dashboard bounces to auth', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/sign-in|sign-up|\/$/, { timeout: 15_000 });
  });
});
