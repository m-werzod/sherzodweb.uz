/**
 * POST /api/onboarding/cadence
 *
 * Captures the user's posting cadence + weekly time budget mid-onboarding
 * (shown as a side card on /onboarding/loading while the pipeline runs).
 * Writes to OnboardingProfile.postingCadence / weeklyHoursBudget. The
 * scriptwriter agent reads these on subsequent runs to batch tasks more
 * realistically.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

const Body = z.object({
  cadence: z.enum(['low', 'medium', 'high']),
  weeklyHours: z.number().int().min(1).max(80).optional(),
});

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const json = await req.json().catch(() => null);
  const parsed = Body.safeParse(json);
  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid' }, { status: 400 });
  }

  const db = prismaForTenant(session.user.tenantId);
  // Find the most recently-created onboarding profile for this tenant.
  const profile = await db.onboardingProfile.findFirst({
    orderBy: { createdAt: 'desc' },
  });
  if (!profile) {
    return NextResponse.json({ error: 'no_profile' }, { status: 404 });
  }

  // Raw SQL — postingCadence / weeklyHoursBudget were added without a
  // prisma migrate cycle, so the generated client may not type them yet.
  // Once the dev box runs `prisma generate` the typed call will work too.
  // We use parameterized $executeRaw to avoid SQL injection.
  await db.$executeRaw`
    UPDATE onboarding_profiles
    SET "postingCadence" = ${parsed.data.cadence},
        "weeklyHoursBudget" = ${parsed.data.weeklyHours ?? null}
    WHERE id = ${profile.id}
  `;

  return NextResponse.json({ ok: true });
}
