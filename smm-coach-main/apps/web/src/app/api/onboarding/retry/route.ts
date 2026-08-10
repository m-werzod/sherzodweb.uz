/**
 * POST /api/onboarding/retry
 *
 * Re-dispatches roadmap_generation for the current tenant using their
 * existing OnboardingProfile. Used by the loading page's error UI when
 * the first run failed (LLM outage, budget cap, timeout) or got lost
 * during dispatch.
 *
 * Idempotency-keyed per 10-min window like the original onboarding POST.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { invokeWorkflow } from '@/lib/agents/client';

export async function POST() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const db = prismaForTenant(session.user.tenantId);

  // Find the latest IG account + onboarding profile to reconstruct the
  // workflow payload. The original onboarding POST does this from the
  // wizard form; we read it back from DB.
  const profile = await db.onboardingProfile.findFirst({
    orderBy: { createdAt: 'desc' },
    include: { instagramAccount: { select: { handle: true } } },
  });
  if (!profile) {
    return NextResponse.json({ error: 'no_profile' }, { status: 400 });
  }

  const onboardingPayload = {
    instagramHandle: profile.instagramAccount?.handle ?? '',
    niche: profile.niche,
    subNiche: profile.subNiche ?? undefined,
    // nicheDetail + the goal taxonomy + cadence were DROPPED here, so a retry silently produced a
    // differently-sized roadmap with the legacy 60/30/10 funnel instead of the wizard's promise —
    // and initial_analysis reads north_star ONLY from this payload (never re-reads the DB). Mirror
    // the primary POST's parsed.data so retry rebuilds the SAME roadmap the user was shown.
    nicheDetail: profile.nicheDetail ?? undefined,
    contentStyle: profile.contentStyle ?? undefined,
    targetAudience: profile.targetAudience ?? '',
    brandVoice: profile.brandVoice ?? undefined,
    currentFollowers: profile.currentFollowers,
    targetFollowers: profile.targetFollowers,
    deadline: profile.deadline?.toISOString() ?? undefined,
    primaryGoal: profile.primaryGoal ?? undefined,
    secondaryGoal: profile.secondaryGoal ?? undefined,
    goalWeight: profile.goalWeight ?? undefined,
    postsPerDay: profile.postsPerDay ?? undefined,
    locale: 'uz' as const,
  };

  const run = await invokeWorkflow({
    tenantId: session.user.tenantId,
    userId: session.user.id,
    workflow: 'roadmap_generation',
    input: { onboarding: onboardingPayload, retry: true },
    idempotencyKey: `retry:${session.user.tenantId}:${Math.floor(Date.now() / (10 * 60 * 1000))}`,
  });

  return NextResponse.json({ ok: true, run });
}
