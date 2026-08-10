/**
 * POST /api/onboarding/analyze-posts — analyse the connected account's seeded
 * posts (engagement health + content topics) and cache it on InstagramAccount.
 * Thin wrapper over ensurePostAnalysis (shared with /api/onboarding so the
 * analysis runs no matter which onboarding path the user took).
 *
 * Returns { analysis: PastPostsAnalysis | null } (null when there's no connected
 * account or no posts yet — the onboarding chat then just skips the analysis).
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { ensurePostAnalysis } from '@/lib/instagram/run-analysis';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const analysis = await ensurePostAnalysis(session.user.tenantId).catch(() => null);
  return NextResponse.json({ analysis });
}
