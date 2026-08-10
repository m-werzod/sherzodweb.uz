/**
 * GET /api/instagram/me — the logged-in user's connected Instagram account
 * (handle + follower count). Used by the signup chat to resume after the IG
 * OAuth round-trip: once connected we read the real follower count from the
 * account the callback just wrote, instead of re-probing anonymously.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ connected: false });
  }
  const db = prismaForTenant(session.user.tenantId);
  const acct = await db.instagramAccount.findFirst({
    orderBy: { createdAt: 'desc' },
    select: { handle: true, followerCount: true, postsCount: true, verified: true },
  });
  if (!acct) return NextResponse.json({ connected: false });
  return NextResponse.json({
    connected: true,
    handle: acct.handle,
    followers: acct.followerCount ?? 0,
    posts: acct.postsCount ?? 0,
    verified: acct.verified,
  });
}
