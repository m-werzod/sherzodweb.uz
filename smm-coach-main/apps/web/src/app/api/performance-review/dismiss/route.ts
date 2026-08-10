/**
 * POST /api/performance-review/dismiss — dismiss an OPEN performance review.
 *
 * Body: { id?: string }. With an id, dismisses just that alert (so closing a
 * breakout banner doesn't also clear an open underperform one). Without it,
 * dismisses every open review for the tenant (legacy "clear all" behaviour).
 * Stamps dismissedAt so the history is auditable.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const id = await req
    .json()
    .then((b) => (typeof b?.id === 'string' ? b.id : null))
    .catch(() => null);

  const db = prismaForTenant(session.user.tenantId);
  const { count } = await db.performanceReview.updateMany({
    where: { status: 'open', ...(id ? { id } : {}) },
    data: { status: 'dismissed', dismissedAt: new Date() },
  });
  return NextResponse.json({ ok: true, dismissed: count });
}
