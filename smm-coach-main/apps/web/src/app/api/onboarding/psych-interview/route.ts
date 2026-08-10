import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { getPsychInterview, type InterviewMsg } from '@/lib/agents/client';

/**
 * Proxy for the deep psychological onboarding interview (Dizayn A). The browser
 * holds the conversation and posts the full history each turn; we forward it to
 * the agents service (HMAC-signed, server-only) and return the next question.
 *
 * The transcript is persisted to the standalone PsychInterview row (the
 * OnboardingProfile doesn't exist yet at this point in onboarding) — find-first
 * then update-or-create, since PsychInterview has no per-tenant unique key.
 */
/**
 * Resume support — return the latest INCOMPLETE interview's transcript so a refresh
 * or re-entry mid-interview continues instead of starting over (completion incentive).
 * Empty messages when there's nothing to resume → the client starts fresh.
 */
export async function GET() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  try {
    const db = prismaForTenant(session.user.tenantId);
    const existing = await db.psychInterview.findFirst({
      where: { completedAt: null },
      orderBy: { createdAt: 'desc' },
      select: { messages: true },
    });
    const messages = Array.isArray(existing?.messages) ? existing!.messages : [];
    return NextResponse.json({ messages });
  } catch {
    return NextResponse.json({ messages: [] });
  }
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const body = (await req.json().catch(() => null)) as {
    history?: InterviewMsg[];
    coveredDims?: string[];
    niche?: string;
    nicheDetail?: string;
    targetAudience?: string;
  } | null;
  const history = Array.isArray(body?.history) ? body!.history : [];

  let turn;
  try {
    turn = await getPsychInterview(session.user.tenantId, history, {
      coveredDims: body?.coveredDims ?? [],
      niche: body?.niche,
      nicheDetail: body?.nicheDetail,
      targetAudience: body?.targetAudience,
    });
  } catch {
    // Best-effort: signal `done` so the onboarding chat skips the psych phase
    // gracefully instead of stalling when the agents service is unavailable.
    return NextResponse.json({ done: true, question: null });
  }

  // Persist the running transcript (resume / audit). Best-effort — a DB hiccup
  // must never break the interview.
  try {
    const db = prismaForTenant(session.user.tenantId);
    const existing = await db.psychInterview.findFirst({
      where: { completedAt: null },
      orderBy: { createdAt: 'desc' },
    });
    if (existing) {
      await db.psychInterview.update({ where: { id: existing.id }, data: { messages: history } });
    } else {
      await db.psychInterview.create({
        data: { tenantId: session.user.tenantId, messages: history },
      });
    }
  } catch {
    /* best-effort */
  }

  return NextResponse.json(turn);
}
