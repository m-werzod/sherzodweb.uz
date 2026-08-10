import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { extractPsychProfile, type InterviewMsg } from '@/lib/agents/client';

/**
 * Distil the finished psychological interview into a UserPsychProfile and store
 * it on the PsychInterview row (completed). The /api/onboarding submit later
 * copies it onto OnboardingProfile.psychProfile once that row exists.
 */
export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const body = (await req.json().catch(() => null)) as
    | { history?: InterviewMsg[]; bfi10?: Record<string, number> }
    | null;
  const history = Array.isArray(body?.history) ? body!.history : [];
  if (history.length === 0) {
    return NextResponse.json({ ok: false, profile: null });
  }
  // Validated BFI-10 answers (item id → 1-5), if the user completed the sliders.
  const bfi10 =
    body?.bfi10 && typeof body.bfi10 === 'object' ? (body.bfi10 as Record<string, number>) : undefined;

  let profile: Record<string, unknown> | null = null;
  try {
    const out = await extractPsychProfile(session.user.tenantId, history, bfi10);
    profile = out.profile;
  } catch {
    return NextResponse.json({ ok: false, profile: null });
  }

  // Persist onto the latest interview row (best-effort).
  try {
    const db = prismaForTenant(session.user.tenantId);
    const existing = await db.psychInterview.findFirst({ orderBy: { createdAt: 'desc' } });
    if (existing) {
      await db.psychInterview.update({
        where: { id: existing.id },
        data: { messages: history, profile: profile ?? undefined, completedAt: new Date() },
      });
    } else {
      await db.psychInterview.create({
        data: {
          tenantId: session.user.tenantId,
          messages: history,
          profile: profile ?? undefined,
          completedAt: new Date(),
        },
      });
    }
  } catch {
    /* best-effort */
  }

  return NextResponse.json({ ok: true, profile });
}
