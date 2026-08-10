/**
 * GET /api/onboarding/status
 *
 * Tells the /onboarding/loading page what to do next.
 *
 * Returns:
 *   roadmapReady   — true once a roadmap with status='active' exists.
 *                    Loading page redirects to /dashboard on this.
 *   onboardingDone — true once an OnboardingProfile row exists (sanity).
 *   runStatus      — latest roadmap_generation run state. 'failed' →
 *                    show error UI with retry. 'running'/'queued' →
 *                    keep waiting. 'completed' but no roadmap → schema
 *                    mismatch, treat as failed.
 *   runStartedAt   — ISO timestamp; client computes elapsed for the
 *                    "longer than expected" warning at 5+ minutes.
 *   errorMessage   — set when runStatus='failed' so the UI can surface
 *                    what went wrong (LLM timeout, budget, etc.).
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const db = prismaForTenant(session.user.tenantId);

  const [profileCount, roadmap, run] = await Promise.all([
    db.onboardingProfile.count({ take: 1 }),
    db.roadmap.findFirst({
      where: { status: 'active' },
      select: { id: true },
    }),
    db.agentRun.findFirst({
      where: { workflow: 'roadmap_generation' },
      orderBy: { startedAt: 'desc' },
      select: {
        id: true,
        status: true,
        startedAt: true,
        error: true,
      },
    }),
  ]);

  // Run finished but no active roadmap was persisted (empty approved set /
  // schema mismatch / idempotency-reuse of an empty run). Per the contract
  // above, treat as failed so the loading page shows the retry UI instead of
  // polling forever. Only once a profile exists (a real attempt) — not during
  // the brief window before the first run row appears.
  const completedNoRoadmap = run?.status === 'completed' && !roadmap && profileCount > 0;

  return NextResponse.json({
    onboardingDone: profileCount > 0,
    roadmapReady: Boolean(roadmap),
    runStatus: completedNoRoadmap ? 'failed' : (run?.status ?? null),
    runStartedAt: run?.startedAt?.toISOString() ?? null,
    errorMessage: completedNoRoadmap
      ? "Yo'l xaritasi yaratildi-yu, saqlanmadi. Qayta urinib ko'ring."
      : (run?.error ?? null),
  });
}
