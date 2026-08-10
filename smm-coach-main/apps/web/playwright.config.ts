import { defineConfig, devices } from '@playwright/test';

/**
 * Smoke E2E for SMM Coach (S3.7). Runs against a DEPLOYED url (no local
 * webServer) so it doubles as a post-deploy gate.
 *
 *   One-time setup:  pnpm --filter @smm/web add -D @playwright/test
 *                    pnpm --filter @smm/web exec playwright install chromium
 *   Run:             E2E_BASE_URL=https://smm.brotech.uz pnpm --filter @smm/web test:e2e
 *
 * Scope = public surface + mobile no-overflow — the HIGH-FREQUENCY regression
 * surface (a deploy breaking a page, a layout overflowing on phones — exactly
 * the classes of bug this project repeatedly hit). The DEEP agent funnel
 * (onboarding → roadmap → Opus script → tracker_pulse → comment_sentinel)
 * takes ~5 min + real LLM cost + a seeded test tenant + cleanup, so it belongs
 * in a separate gated suite against a staging DB — NOT this fast smoke.
 *
 * This file + ./e2e live OUTSIDE src/, so they are excluded from `tsc` and the
 * Next production build (tsconfig include = src only) — zero deploy impact.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'https://smm.brotech.uz',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['iPhone 13'] } },
  ],
});
