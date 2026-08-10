/**
 * Profile review — first stop after Instagram OAuth. Loads the latest
 * profile audit from DB (running a fresh one if none exists yet), then
 * delegates to the client view that owns the re-check / done / skip
 * interactions. Score gates progress to /dashboard.
 */
import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { decryptToken } from '@/lib/security/crypto';
import { fetchProfile } from '@/lib/instagram/graph-api-client';
import type { ProfileAudit } from '@/lib/instagram/profile-audit';
import { dispatchProfileAudit } from '@/lib/instagram/audit-dispatch';
import { ProfileReviewView } from '@/components/onboarding/profile-review-view';

export const dynamic = 'force-dynamic';

export default async function ProfileReviewPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  const params = await searchParams;
  const igError = typeof params.ig_error === 'string' ? params.ig_error : null;

  // Personal-account error from the OAuth callback — show step-by-step
  // recovery instead of the audit (we don't have a token at all in this
  // case because we bailed out before upserting InstagramAccount).
  if (igError === 'personal_account') {
    return <PersonalAccountError />;
  }

  const db = prismaForTenant(session.user.tenantId);
  const ig = await db.instagramAccount.findFirst({ orderBy: { createdAt: 'desc' } });
  if (!ig?.oauthAccessTokenEnc) {
    // Token missing — bounce back to dashboard so the connect banner is
    // visible. (Most likely the user landed here without completing OAuth.)
    redirect('/dashboard');
  }

  // Decrypt + fetch profile fresh so the page mirrors what's on Instagram
  // *right now*. Cached values may be stale (user could have edited bio
  // between sessions).
  let audit: ProfileAudit | null = (ig.profileAudit ?? null) as ProfileAudit | null;
  let liveProfile: {
    id: string;
    username: string;
    name?: string;
    biography?: string;
    profile_picture_url?: string;
    followers_count?: number;
    follows_count?: number;
    media_count?: number;
    account_type?: string;
  } = {
    id: ig.instagramUserId ?? '',
    username: ig.handle,
    biography: ig.bio ?? undefined,
    profile_picture_url: ig.avatarUrl ?? undefined,
    followers_count: ig.followerCount,
    follows_count: ig.followingCount,
    media_count: ig.postsCount,
    account_type: String(ig.accountType),
  };

  try {
    const token = decryptToken(ig.oauthAccessTokenEnc);
    const fresh = await fetchProfile(token);
    liveProfile = { ...liveProfile, ...fresh };
    // If we don't have an audit yet, dispatch one to the agents service and
    // wait briefly for it so the page renders with suggestions instead of an
    // empty checklist. The node merges prior progress + writes profileAudit.
    if (!audit) {
      const onboarding = await db.onboardingProfile.findFirst({ orderBy: { createdAt: 'desc' } });
      audit = await dispatchProfileAudit({
        tenantId: session.user.tenantId,
        userId: session.user.id,
        igAccountId: ig.id,
        profile: fresh,
        niche: onboarding?.niche ?? null,
        goal: onboarding
          ? { current: onboarding.currentFollowers, target: onboarding.targetFollowers, months: 6 }
          : null,
        priorGeneratedAt: null,
        wait: true,
      });
    }
  } catch (err) {
    console.error('[profile-review] live fetch failed:', err);
    // Render page with whatever cached data we have; client can re-trigger.
  }

  return <ProfileReviewView profile={liveProfile} audit={audit} />;
}

function PersonalAccountError() {
  return (
    <div style={{ maxWidth: 640, margin: '60px auto', padding: 32 }}>
      <div
        className="card"
        style={{
          padding: 28,
          borderColor: 'var(--color-bad, #EF4444)',
          background: 'color-mix(in oklch, var(--color-bad, #EF4444) 5%, transparent)',
        }}
      >
        <div style={{ fontSize: 36, marginBottom: 8 }}>⚠️</div>
        <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 10 }}>
          Instagram akkauntingiz Personal turida
        </h1>
        <p className="muted" style={{ fontSize: 14, marginBottom: 20, lineHeight: 1.6 }}>
          SMM Coach ishlashi uchun sizning Instagram akkauntingiz <strong>Professional</strong>{' '}
          (<strong>Business</strong> yoki <strong>Creator</strong>) bo'lishi shart. Personal
          akkauntda Graph API insights, comment moderation va boshqa funksiyalar ishlamaydi.
        </p>

        <div
          style={{
            background: 'rgba(255,255,255,0.03)',
            borderRadius: 10,
            padding: 18,
            marginBottom: 20,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}>
            Qanday o'tkazish (2 daqiqa):
          </div>
          <ol style={{ paddingLeft: 22, fontSize: 13, lineHeight: 1.8 }}>
            <li>Instagram ilovasini oching → profilingizga o'ting</li>
            <li>Yuqori o'ng burchakdagi <strong>☰ menyusi</strong> → <strong>Settings and activity</strong></li>
            <li>Pastga aylantirib → <strong>For professionals</strong> → <strong>Account type and tools</strong></li>
            <li><strong>Switch to professional account</strong> bosing</li>
            <li>Kategoriya tanlang (masalan: <em>Personal Blog</em>, <em>Product/Service</em>)</li>
            <li><strong>Creator</strong> yoki <strong>Business</strong>'ni tanlang</li>
            <li>Facebook Page'ga ulanish so'raladi — <strong>Skip yoki yangi yarating</strong></li>
            <li>Tugagach, shu sahifaga qayting va qaytadan ulaning</li>
          </ol>
        </div>

        {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
        <a
          href="/api/auth/instagram/start"
          className="btn primary"
          style={{ display: 'inline-block' }}
        >
          Qaytadan ulashga harakat qilish →
        </a>
      </div>
    </div>
  );
}
