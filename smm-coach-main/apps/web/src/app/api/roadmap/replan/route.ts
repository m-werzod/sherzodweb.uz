/**
 * POST /api/roadmap/replan
 *
 * Throws away the current active roadmap and asks the agent loop to
 * generate a fresh one. Use cases:
 *   • User changed their niche / goal during onboarding
 *   • Generated scripts feel off-brand and per-task regen isn't enough
 *   • A milestone hit, time to reset expectations
 *
 * The agents-side `replan` workflow:
 *   1. Archives current roadmap (status = 'archived').
 *   2. Re-runs initial_analysis + roadmap_generator with latest IG data.
 *   3. Writes the new active roadmap; UI auto-refreshes via the existing
 *      poll.
 *
 * Rate-limited to once per 6 hours per tenant (this is an expensive call,
 * burning ~$2 in Opus + Sonnet).
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { invokeWorkflow } from '@/lib/agents/client';
import { notifyTelegram } from '@/lib/telegram';
import { REPLAN_COOLDOWN_HOURS, checkReplanCooldown } from '@/lib/roadmap/replan-cooldown';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const cooldown = await checkReplanCooldown(session.user.tenantId);
  if (cooldown.active) {
    const hoursAgo = cooldown.hoursAgo;
    void notifyTelegram(
      `⏰ Roadmap replan rad etildi · cooldown · tenant=${session.user.tenantId} · last=${hoursAgo}h oldin`,
    );
    return NextResponse.json(
      {
        error: 'cooldown',
        message: `Yo'l xaritasini qayta tuzish ${REPLAN_COOLDOWN_HOURS} soatda 1 marta. So'nggi marta ${hoursAgo} soat oldin.`,
        retryAfterMinutes: REPLAN_COOLDOWN_HOURS * 60 - Math.floor(hoursAgo * 60),
      },
      { status: 429 },
    );
  }

  const run = await invokeWorkflow({
    tenantId: session.user.tenantId,
    userId: session.user.id,
    workflow: 'replan',
    input: { reason: 'user_requested' },
    idempotencyKey: `replan:${session.user.tenantId}:${Math.floor(Date.now() / (60 * 60 * 1000))}`,
  });

  void notifyTelegram(
    `🌳 Roadmap replan · tenant=${session.user.tenantId} · runId=${run.runId} · user_requested`,
  );

  return NextResponse.json({ ok: true, run });
}
