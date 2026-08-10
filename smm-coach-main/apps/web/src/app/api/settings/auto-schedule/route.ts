/**
 * POST /api/settings/auto-schedule — toggle cadence auto-queue (Stage 11).
 * Body: { enabled }. When ON, the autoqueue cron creates ScheduledPosts for
 * FINALIZED tasks at AI best-time slots, up to the user's cadence. Default OFF
 * because this AUTO-PUBLISHES to the real IG account — explicit opt-in. Every
 * scheduled post stays visible + cancelable before it fires.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const BodySchema = z.object({ enabled: z.boolean() });

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const parsed = BodySchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid' }, { status: 400 });
  }
  const db = prismaForTenant(session.user.tenantId);
  const { count } = await db.onboardingProfile.updateMany({
    data: { autoSchedule: parsed.data.enabled },
  });
  return NextResponse.json({ ok: true, updated: count, enabled: parsed.data.enabled });
}
