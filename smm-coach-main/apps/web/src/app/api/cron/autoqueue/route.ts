/**
 * POST /api/cron/autoqueue — Stage 11 cadence auto-queue.
 *
 * Session-less: authorized by x-cron-secret (the agents autoqueue_scheduler
 * worker calls it). For every tenant that opted into autoSchedule, top up their
 * ScheduledPosts toward the posting cadence using finalized tasks + AI best-time
 * slots. The actual publishing is still done by /api/cron/publish-due when each
 * scheduled time arrives — this route only QUEUES (visible + cancelable rows).
 */
import { timingSafeEqual } from 'node:crypto';
import { NextResponse } from 'next/server';
import { prisma, prismaForTenant } from '@smm/db';
import { runAutoqueueForTenant } from '@/lib/scheduling/autoqueue';

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

  // Cross-tenant read (raw prisma) to find who opted in; per-tenant work is
  // tenant-scoped via prismaForTenant below.
  const optedIn = await prisma.onboardingProfile.findMany({
    where: { autoSchedule: true },
    select: { tenantId: true },
  });

  let scheduled = 0;
  let tenantsTouched = 0;
  for (const p of optedIn) {
    try {
      const db = prismaForTenant(p.tenantId);
      // ScheduledPost.userId is optional; the publish path keys off tenantId.
      const n = await runAutoqueueForTenant(db, p.tenantId, null);
      scheduled += n;
      if (n > 0) tenantsTouched += 1;
    } catch {
      // One tenant's failure must not block the rest — skip + continue.
    }
  }

  return NextResponse.json({ ok: true, tenants: optedIn.length, tenantsTouched, scheduled });
}
