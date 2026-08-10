/**
 * GET  /api/instagram/profile-audit  → return latest stored audit
 * POST /api/instagram/profile-audit  → run a fresh audit via the agents service
 *
 * Both require an authenticated session AND a connected Instagram account
 * with a valid OAuth token (oauthAccessTokenEnc). The fresh-audit path
 * decrypts the token, hits Graph API /me for current profile data, then
 * dispatches the `profile_audit_pulse` workflow — the LLM call lives in the
 * agents service (profile_auditor node) so it shows up in the AI Inspector.
 * We then short-poll the DB until the node writes the fresh audit (the merge
 * of prior done/skipped items happens server-side in the node).
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { decryptToken } from '@/lib/security/crypto';
import { fetchProfile } from '@/lib/instagram/graph-api-client';
import type { ProfileAudit } from '@/lib/instagram/profile-audit';
import { dispatchProfileAudit } from '@/lib/instagram/audit-dispatch';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const db = prismaForTenant(session.user.tenantId);
  const ig = await db.instagramAccount.findFirst({ orderBy: { createdAt: 'desc' } });
  if (!ig) {
    return NextResponse.json({ error: 'no_account' }, { status: 404 });
  }
  return NextResponse.json({
    audit: (ig.profileAudit ?? null) as ProfileAudit | null,
    connected: Boolean(ig.oauthAccessTokenEnc),
    handle: ig.handle,
  });
}

export async function POST() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const db = prismaForTenant(session.user.tenantId);
  const ig = await db.instagramAccount.findFirst({ orderBy: { createdAt: 'desc' } });
  if (!ig?.oauthAccessTokenEnc) {
    return NextResponse.json({ error: 'no_oauth' }, { status: 400 });
  }
  const onboarding = await db.onboardingProfile.findFirst({ orderBy: { createdAt: 'desc' } });

  try {
    const token = decryptToken(ig.oauthAccessTokenEnc);
    const profile = await fetchProfile(token);

    // Refresh cached profile fields while we have the live data — independent
    // of the audit, so the dashboard's follower count is fresh either way.
    const priorGeneratedAt =
      ((ig.profileAudit ?? null) as ProfileAudit | null)?.generatedAt ?? null;
    await db.instagramAccount.update({
      where: { id: ig.id },
      data: {
        followerCount: profile.followers_count ?? ig.followerCount,
        followingCount: profile.follows_count ?? ig.followingCount,
        postsCount: profile.media_count ?? ig.postsCount,
        bio: profile.biography ?? ig.bio,
        avatarUrl: profile.profile_picture_url ?? ig.avatarUrl,
        lastSyncedAt: new Date(),
      },
    });

    const months = onboarding?.deadline
      ? Math.max(1, Math.round((onboarding.deadline.getTime() - Date.now()) / (30 * 86_400_000)))
      : 6;

    // Dispatch to the agents service (profile_auditor node runs Claude, merges
    // prior done/skipped items, writes profileAudit) and short-poll until it
    // lands — keeps the existing synchronous UX without the LLM call here.
    const audit = await dispatchProfileAudit({
      tenantId: session.user.tenantId,
      userId: session.user.id,
      igAccountId: ig.id,
      profile,
      niche: onboarding?.niche ?? null,
      goal: onboarding
        ? { current: onboarding.currentFollowers, target: onboarding.targetFollowers, months }
        : null,
      priorGeneratedAt,
      wait: true,
    });
    if (audit) return NextResponse.json({ audit });

    // Still processing — the UI can GET again shortly to pick it up.
    return NextResponse.json({ status: 'processing' }, { status: 202 });
  } catch (err) {
    console.error('[profile-audit]', err);
    return NextResponse.json(
      { error: 'audit_failed', detail: err instanceof Error ? err.message : 'unknown' },
      { status: 500 },
    );
  }
}
