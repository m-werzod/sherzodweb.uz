/**
 * GET /api/leads — sales-funnel inbox feed (Stage 12).
 *
 * Returns this tenant's detected leads (sales/interest comments) with the
 * AI-drafted reply, newest first. Query params:
 *   status — new | contacted | converted | dismissed (default: all)
 *   limit  — max rows (default 100, capped at 200)
 *
 * Also returns per-status counts so the UI can render tabs + the nav badge.
 * Tenant-scoped via prismaForTenant.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';

const STATUSES = ['new', 'contacted', 'converted', 'dismissed'] as const;
type LeadStatus = (typeof STATUSES)[number];

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const url = new URL(req.url);
  const statusParam = url.searchParams.get('status');
  const status = (STATUSES as readonly string[]).includes(statusParam ?? '')
    ? (statusParam as LeadStatus)
    : undefined;
  const limit = Math.min(Number(url.searchParams.get('limit') ?? 100) || 100, 200);

  const db = prismaForTenant(session.user.tenantId);

  const [leads, grouped] = await Promise.all([
    db.lead.findMany({
      where: status ? { status } : {},
      orderBy: { createdAt: 'desc' },
      take: limit,
      select: {
        id: true,
        igUsername: true,
        commentText: true,
        intent: true,
        status: true,
        taskId: true,
        postId: true,
        draftReply: true,
        notes: true,
        createdAt: true,
      },
    }),
    db.lead.groupBy({ by: ['status'], _count: { _all: true } }),
  ]);

  const counts: Record<LeadStatus, number> = {
    new: 0,
    contacted: 0,
    converted: 0,
    dismissed: 0,
  };
  for (const g of grouped) {
    counts[g.status as LeadStatus] = g._count._all;
  }

  return NextResponse.json({ ok: true, leads, counts });
}
