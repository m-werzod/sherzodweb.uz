/**
 * GET /api/performance-review/latest — the most important OPEN performance
 * review for this tenant (or null). Drives the dashboard PerformanceBanner.
 *
 * Stage 13 — the agent loop now raises several alert KINDS (underperform,
 * breakout, negative_wave). We surface ONE at a time, picking the highest
 * severity first (then most recent) so the user sees the most urgent signal;
 * dismissing it reveals the next.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const SEVERITY_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

export async function GET() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ review: null });
  }
  const db = prismaForTenant(session.user.tenantId);
  // Dedup keeps the open set tiny; fetch a handful and rank in JS since
  // severity is a string Prisma can't custom-order.
  const open = await db.performanceReview.findMany({
    where: { status: 'open' },
    orderBy: { createdAt: 'desc' },
    take: 12,
    select: {
      id: true,
      kind: true,
      severity: true,
      taskId: true,
      underperformedCount: true,
      rootCauses: true,
      recommendedPivots: true,
      payload: true,
      createdAt: true,
    },
  });

  const review =
    open
      .slice()
      .sort(
        (a, b) =>
          (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0) ||
          b.createdAt.getTime() - a.createdAt.getTime(),
      )[0] ?? null;

  return NextResponse.json({ review });
}
