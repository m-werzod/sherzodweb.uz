/**
 * POST /api/media/generate — start a Higgsfield generation for this tenant.
 *
 * Body: { kind, prompt, taskId?, imageUrl?, audioUrl?, aspect?, model? }
 *   image2video → needs imageUrl   · text2image → prompt only (+optional ref)
 *   speak       → needs imageUrl + audioUrl
 *
 * Submits async (returns in seconds, not minutes) and persists a MediaGeneration
 * row. The client then polls GET /api/media/[id] until completed. Generation
 * spends Higgsfield credits, so this is gated behind a configured key.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { notifyTelegram } from '@/lib/telegram';
import { higgsfieldConfigured } from '@/lib/higgsfield/client';
import { startGeneration } from '@/lib/higgsfield/service';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// Each generation spends real Higgsfield credits, so cap how many a tenant can
// kick off per rolling hour — a buggy client loop or rapid clicks can't drain
// the account. Generous enough for normal iterative use.
const HOURLY_CAP = 30;

const BodySchema = z.object({
  kind: z.enum(['image2video', 'text2image', 'speak']),
  prompt: z.string().trim().min(1, 'Prompt kerak').max(2000),
  taskId: z.string().optional(),
  imageUrl: z.string().url().optional(),
  audioUrl: z.string().url().optional(),
  aspect: z.string().optional(),
  model: z.enum(['dop-lite', 'dop-turbo', 'dop-standard']).optional(),
});

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  if (!higgsfieldConfigured()) {
    return NextResponse.json(
      { error: 'not_configured', message: 'Higgsfield kaliti sozlanmagan (HF_CREDENTIALS).' },
      { status: 503 },
    );
  }

  const parsed = BodySchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'invalid', message: parsed.error.issues[0]?.message ?? 'invalid body' },
      { status: 400 },
    );
  }

  // Per-tenant hourly rate limit (credit-drain guard).
  const db = prismaForTenant(session.user.tenantId);
  const recent = await db.mediaGeneration.count({
    where: { createdAt: { gte: new Date(Date.now() - 60 * 60 * 1000) } },
  });
  if (recent >= HOURLY_CAP) {
    return NextResponse.json(
      {
        error: 'rate_limited',
        message: `Soatiga ${HOURLY_CAP} ta generatsiya chegarasi. Biroz keyinroq urinib koʻring.`,
      },
      { status: 429 },
    );
  }

  const result = await startGeneration(session.user.tenantId, session.user.id ?? null, parsed.data);
  if (!result.ok) {
    const sc = result.statusCode;
    void notifyTelegram(
      `🎬 higgsfield/${parsed.data.kind} · ${session.user.tenantId} · ❌ ${result.error.slice(0, 150)}`,
    );
    return NextResponse.json(
      { error: 'generation_failed', message: result.error, status: sc },
      { status: sc && sc >= 400 && sc < 500 ? sc : 502 },
    );
  }
  void notifyTelegram(
    `🎬 higgsfield/${result.kind} · ${session.user.tenantId} · ${result.status} · gen=${result.id}`,
  );
  return NextResponse.json(result);
}
