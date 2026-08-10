/**
 * GET /api/media/[id] — current status of a MediaGeneration.
 *
 * If the job isn't terminal yet, this polls Higgsfield once, persists any
 * progress (status, resultUrl), and returns the fresh state. The brief UI polls
 * this every few seconds until status is terminal. Best-effort: a poll failure
 * returns the last-known row rather than erroring.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { pollGeneration, resultUrl } from '@/lib/higgsfield/client';
import { TERMINAL_STATUSES, type HiggsfieldStatus } from '@/lib/higgsfield/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const { id } = await ctx.params;
  const db = prismaForTenant(session.user.tenantId);

  const row = await db.mediaGeneration.findFirst({
    where: { id },
    select: {
      id: true,
      kind: true,
      status: true,
      resultUrl: true,
      requestId: true,
      error: true,
      createdAt: true,
    },
  });
  if (!row) return NextResponse.json({ error: 'not_found' }, { status: 404 });

  // Already done, or nothing to poll → return as-is.
  if (TERMINAL_STATUSES.has(row.status as HiggsfieldStatus) || !row.requestId) {
    return NextResponse.json({ ok: true, ...publicView(row) });
  }

  try {
    const res = await pollGeneration(row.requestId);
    const url = resultUrl(res);
    const updated = await db.mediaGeneration.update({
      where: { id: row.id },
      data: {
        status: res.status,
        resultUrl: url ?? row.resultUrl,
        // bounded result only — not the whole response (avoids jsonb bloat)
        result: { status: res.status, images: res.images ?? null, video: res.video ?? null },
        error: res.status === 'failed' ? 'generation failed' : res.status === 'nsfw' ? 'nsfw' : null,
      },
      select: { id: true, kind: true, status: true, resultUrl: true, error: true },
    });
    return NextResponse.json({ ok: true, ...updated });
  } catch {
    // poll hiccup — hand back the last-known state, let the client retry.
    return NextResponse.json({ ok: true, ...publicView(row) });
  }
}

/** The client never needs the internal provider requestId. */
function publicView(row: {
  id: string;
  kind: string;
  status: string;
  resultUrl: string | null;
  error: string | null;
}) {
  return { id: row.id, kind: row.kind, status: row.status, resultUrl: row.resultUrl, error: row.error };
}
