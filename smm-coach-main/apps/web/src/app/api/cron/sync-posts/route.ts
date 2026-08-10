/**
 * POST /api/cron/sync-posts — re-sync every connected account's RECENT Instagram
 * media so a post published directly on Instagram (after the connect-time sync)
 * shows up in the dashboard automatically, instead of only at OAuth connect.
 *
 * Session-less: authorized by x-cron-secret (the caller is the agents
 * post_sync_scheduler worker). New-posts-only per account, so it's cheap to run
 * on a schedule. Needs the account's OAuth token (own-media edge).
 */
import { timingSafeEqual } from 'node:crypto';
import { NextResponse } from 'next/server';
import { prisma } from '@smm/db';
import { refreshPostMetrics, syncNewPosts } from '@/lib/instagram/sync-account';
import { decryptToken } from '@/lib/security/crypto';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 300;

function authorized(req: Request): boolean {
  const secret = process.env.CRON_SECRET || process.env.AGENTS_HMAC_SECRET || '';
  const given = req.headers.get('x-cron-secret') ?? '';
  if (!secret || !given) return false;
  const a = Buffer.from(secret);
  const b = Buffer.from(given);
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function POST(req: Request) {
  if (!authorized(req)) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const accounts = await prisma.instagramAccount.findMany({
    where: { oauthAccessTokenEnc: { not: null } },
    // Least-recently-synced (or never-synced) first, so if the per-tick budget runs
    // out no account is perpetually starved — each tick advances the oldest ones.
    orderBy: { lastSyncedAt: { sort: 'asc', nulls: 'first' } },
    select: { id: true, tenantId: true, oauthAccessTokenEnc: true },
  });

  let scanned = 0;
  let newPosts = 0;
  let refreshedMetrics = 0;
  let skipped = 0;
  for (const a of accounts) {
    scanned += 1;
    if (!a.oauthAccessTokenEnc) {
      skipped += 1;
      continue;
    }
    let token: string;
    try {
      token = decryptToken(a.oauthAccessTokenEnc);
    } catch {
      skipped += 1;
      continue;
    }
    try {
      newPosts += await syncNewPosts({ tenantId: a.tenantId, igAccountId: a.id, accessToken: token });
    } catch {
      skipped += 1;
    }
    // Existing posts' counters (views/reach/likes) go stale forever without
    // this — the connect-time sync was their only write. Self-throttled via
    // scrapedAt, so most ticks this is a no-op per account.
    try {
      refreshedMetrics += await refreshPostMetrics({
        tenantId: a.tenantId,
        igAccountId: a.id,
        accessToken: token,
      });
    } catch (err) {
      console.warn('[cron/sync-posts] metrics refresh failed:', a.id, (err as Error).message);
    }
  }

  return NextResponse.json({ ok: true, scanned, newPosts, refreshedMetrics, skipped });
}
