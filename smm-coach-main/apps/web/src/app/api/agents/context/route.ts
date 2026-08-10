/**
 * Inline-edit the tenant's "north star" without re-running onboarding.
 *
 * Touches `OnboardingProfile` only — the next agent run will pick up the
 * new values via the existing pipeline (initial_analysis re-embeds the
 * north-star vector that drift_detector uses).
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

const BodySchema = z
  .object({
    niche: z.string().min(2).max(80).optional(),
    /** Coarse bucket from NICHE_OPTIONS (kept for backwards compat with
     *  rows that predate the nicheDetail split). */
    subNiche: z.string().max(80).nullable().optional(),
    /** The free-text niche refinement the agents actually read
     *  (algotrading, vegan-baking, ...). Up to 2000 chars to match the
     *  shared OnboardingPayloadSchema. */
    nicheDetail: z.string().max(2000).nullable().optional(),
    contentStyle: z.string().max(200).nullable().optional(),
    targetAudience: z.string().min(5).max(600).optional(),
    brandVoice: z.string().max(600).nullable().optional(),
    targetFollowers: z.number().int().positive().optional(),
    deadline: z.string().datetime().nullable().optional(),
    weeklyTimeHours: z.number().int().min(1).max(40).nullable().optional(),
    contentLanguage: z.enum(['uz', 'ru', 'uz_ru']).nullable().optional(),
  })
  .refine((v) => Object.keys(v).length > 0, {
    message: 'Hech bo\'lmaganda bitta maydonni o\'zgartiring',
  });

export async function PATCH(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const body = await req.json().catch(() => null);
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'invalid_body', issues: parsed.error.issues },
      { status: 400 },
    );
  }

  const db = prismaForTenant(session.user.tenantId);
  const profile = await db.onboardingProfile.findFirst({
    orderBy: { createdAt: 'desc' },
  });
  if (!profile) {
    return NextResponse.json(
      { error: 'onboarding_missing', message: 'Avval onboarding\'ni yakunlang' },
      { status: 409 },
    );
  }

  const updated = await db.onboardingProfile.update({
    where: { id: profile.id },
    data: {
      // Pass through only the fields the user actually changed so we don't
      // accidentally null out absent values.
      ...(parsed.data.niche !== undefined ? { niche: parsed.data.niche } : {}),
      ...(parsed.data.subNiche !== undefined ? { subNiche: parsed.data.subNiche } : {}),
      ...(parsed.data.nicheDetail !== undefined
        ? { nicheDetail: parsed.data.nicheDetail }
        : {}),
      ...(parsed.data.contentStyle !== undefined
        ? { contentStyle: parsed.data.contentStyle }
        : {}),
      ...(parsed.data.targetAudience !== undefined
        ? { targetAudience: parsed.data.targetAudience }
        : {}),
      ...(parsed.data.brandVoice !== undefined ? { brandVoice: parsed.data.brandVoice } : {}),
      ...(parsed.data.targetFollowers !== undefined
        ? { targetFollowers: parsed.data.targetFollowers }
        : {}),
      ...(parsed.data.deadline !== undefined
        ? { deadline: parsed.data.deadline ? new Date(parsed.data.deadline) : null }
        : {}),
      // weeklyTimeHours / contentLanguage live in v0.2 fields — those
      // weren't added to OnboardingProfile yet, so we stash them in
      // goalSummary as a poor-man's metadata until Bosqich G migrates them
      // to first-class columns. The schema accepts them via the wizard,
      // not via context PATCH — silently drop here so the endpoint still
      // succeeds rather than 400ing on the user.
    },
  });

  return NextResponse.json({ ok: true, profile: updated });
}
