/**
 * POST /api/settings/autopilot — toggle the self-correction autopilot.
 * Body: { enabled }. When ON, a confirmed underperformance auto-applies a replan
 * (coach_supervisor). Default OFF preserves the "user approves" principle.
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
    data: { autopilotReplan: parsed.data.enabled },
  });
  return NextResponse.json({ ok: true, updated: count, enabled: parsed.data.enabled });
}
