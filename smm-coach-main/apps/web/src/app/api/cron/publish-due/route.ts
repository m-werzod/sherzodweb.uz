/**
 * POST /api/cron/publish-due — publish every ScheduledPost whose time has come.
 *
 * Session-less: authorized by a shared secret (x-cron-secret header), since the
 * caller is the agents publish_scheduler worker (or any cron), not a browser.
 * Each due row is atomically claimed → publishTaskNow → status updated. A video
 * still processing is requeued (bounded retries) rather than failed.
 */
import { timingSafeEqual } from 'node:crypto';
import { NextResponse } from 'next/server';
import { prisma } from '@smm/db';
import { publishTaskNow } from '@/lib/instagram/publish';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 300;

const MAX_ATTEMPTS = 5;
// Small batch: each publishTaskNow can poll the IG container up to ~2 min, and
// the loop is serial, so a large batch would blow maxDuration. Slow rows simply
// roll to the next 60s tick (requeue / stale reclaim).
const BATCH = 3;
// A row claimed (status='publishing') but never finalized — the request was
// killed (crash / maxDuration) — is reclaimable after this, so a publish is never
// silently lost. publishTaskNow's own instagramPostId guard still prevents a
// double-post if the kill happened after media_publish.
const STALE_PUBLISHING_MS = 10 * 60 * 1000;

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
  const origin = process.env.NEXTAUTH_URL || new URL(req.url).origin;
  const staleBefore = new Date(Date.now() - STALE_PUBLISHING_MS);

  const due = await prisma.scheduledPost.findMany({
    where: {
      OR: [
        { status: 'pending', scheduledFor: { lte: new Date() } },
        // Reclaim rows stuck mid-publish (crashed/timed-out request).
        { status: 'publishing', updatedAt: { lt: staleBefore } },
      ],
    },
    orderBy: { scheduledFor: 'asc' },
    take: BATCH,
    select: { id: true, tenantId: true, userId: true, taskId: true, attempts: true },
  });

  let published = 0;
  let failed = 0;
  let requeued = 0;
  for (const sp of due) {
    // Atomic claim so two overlapping pollers can't both publish the same row —
    // and so a stale 'publishing' row is reclaimed exactly once.
    const claim = await prisma.scheduledPost.updateMany({
      where: {
        id: sp.id,
        OR: [{ status: 'pending' }, { status: 'publishing', updatedAt: { lt: staleBefore } }],
      },
      data: { status: 'publishing', attempts: { increment: 1 } },
    });
    if (claim.count !== 1) continue;

    const result = await publishTaskNow(sp.tenantId, sp.userId, sp.taskId, origin);
    // already_published / published_partial: the reel IS live on Instagram (a
    // reclaimed row whose first attempt posted before a crash, or a post that
    // went live but failed a later bookkeeping step) — treat as success, never
    // retry, as a retry would be a double-post.
    if (result.ok || result.code === 'already_published' || result.code === 'published_partial') {
      await prisma.scheduledPost.update({
        where: { id: sp.id },
        data: { status: 'published', publishedAt: new Date(), error: null },
      });
      published += 1;
    } else if (result.code === 'processing' && sp.attempts + 1 < MAX_ATTEMPTS) {
      // Video still encoding — requeue for the next poll.
      await prisma.scheduledPost.update({
        where: { id: sp.id },
        data: { status: 'pending', error: result.error },
      });
      requeued += 1;
    } else {
      await prisma.scheduledPost.update({
        where: { id: sp.id },
        data: { status: 'failed', error: result.error },
      });
      failed += 1;
    }
  }

  return NextResponse.json({ ok: true, scanned: due.length, published, requeued, failed });
}
