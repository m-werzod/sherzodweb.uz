/**
 * GET /api/best-time — Stage 11 AI best-time-to-post suggestions.
 *
 * Infers optimal posting slots from this tenant's own published-post history
 * (engagement-weighted, bucketed by UZ-local weekday/hour) and falls back to a
 * researched Uzbekistan-audience heuristic when history is thin.
 *
 * Query: count (default 3, capped 5). Tenant-scoped via prismaForTenant for the
 * account lookup; posts are then filtered by that account's id.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { getBestTime } from '@/lib/scheduling/best-time-data';

export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const url = new URL(req.url);
  const count = Math.min(Math.max(Number(url.searchParams.get('count') ?? 3) || 3, 1), 5);

  const db = prismaForTenant(session.user.tenantId);
  const result = await getBestTime(db, count);
  return NextResponse.json({ ok: true, ...result });
}
