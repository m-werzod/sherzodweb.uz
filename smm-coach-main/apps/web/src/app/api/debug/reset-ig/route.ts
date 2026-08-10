/**
 * POST /api/debug/reset-ig — wipes the current tenant's Instagram footprint
 * so the user can re-run OAuth from a clean slate.
 *
 * Removes:
 *   - InstagramAccount rows for the tenant (cascade → InstagramPost,
 *     and the OAuth token alongside it)
 *   - OnboardingProfile rows (because they're FK'd to InstagramAccount)
 *
 * Leaves: User, Tenant, Roadmap, ContentTask — those are recoverable
 * via the onboarding pipeline once IG is reconnected.
 *
 * Session-required. Tenant-scoped by way of the auth session.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prisma } from '@smm/db';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const tenantId = session.user.tenantId;

  // Find every IG account row for this tenant — both for reporting and
  // so we can drop dependent rows in the right order.
  const igAccounts = await prisma.instagramAccount.findMany({
    where: { tenantId },
    select: { id: true, handle: true, instagramUserId: true },
  });

  // OnboardingProfile FK's instagramAccountId; remove first to avoid
  // an FK violation on the IG account delete.
  const deletedOnboarding = await prisma.onboardingProfile.deleteMany({
    where: { tenantId },
  });

  // Posts are tied to instagramAccountId. Cascade SHOULD handle them,
  // but be explicit for clarity in the logs.
  const accountIds = igAccounts.map((a) => a.id);
  const deletedPosts = accountIds.length
    ? await prisma.instagramPost.deleteMany({
        where: { instagramAccountId: { in: accountIds } },
      })
    : { count: 0 };

  // Now the IG accounts themselves.
  const deletedAccounts = await prisma.instagramAccount.deleteMany({
    where: { tenantId },
  });

  return NextResponse.json({
    ok: true,
    tenantId,
    deleted: {
      instagramAccounts: deletedAccounts.count,
      instagramPosts: deletedPosts.count,
      onboardingProfiles: deletedOnboarding.count,
    },
    previouslyLinked: igAccounts.map((a) => ({
      handle: a.handle,
      instagramUserId: a.instagramUserId,
    })),
    nextSteps: [
      '1. Dashboard → "Instagram\'ni ulash" — yangidan OAuth qiling',
      '2. Agar onboarding wizard kerak bo\'lsa → /onboarding ga kiring',
    ],
  });
}
