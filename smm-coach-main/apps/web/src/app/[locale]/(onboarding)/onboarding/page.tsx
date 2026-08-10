/**
 * Onboarding entry — a conversational, intelligent flow (OnboardingChat).
 * Pre-fills everything we already know (IG account + any prior signup-chat /
 * OnboardingProfile) so nothing is re-asked; the chat only collects what's
 * missing and proposes the audience via AI.
 */
import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { OnboardingChat, type OnboardingChatInitial } from '@/components/onboarding/onboarding-chat';

export const dynamic = 'force-dynamic';

export default async function OnboardingPage({
  searchParams,
}: {
  // ig_account is set by the Instagram OAuth callback ('new' | 'existing' |
  // 'linked') so we can tell the user EXACTLY what the connect did.
  searchParams: Promise<{ ig_account?: string }>;
}) {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');
  const { ig_account: acct } = await searchParams;
  const acctBanner =
    acct === 'new'
      ? {
          accent: false,
          title: 'Yangi hisob yaratildi',
          body: "Instagram orqali yangi SMM Coach hisobi ochildi — bu sizning yangi hisobingiz.",
        }
      : acct === 'existing'
        ? {
            accent: true,
            title: 'Mavjud hisobingizga kirdingiz',
            body: "Bu Instagram avval ro'yxatdan o'tgan hisobga bog'langan edi — yangi hisob ochilmadi.",
          }
        : acct === 'linked'
          ? {
              accent: true,
              title: 'Instagram ulandi',
              body: 'Instagram hisobingiz joriy SMM Coach hisobingizga muvaffaqiyatli ulandi.',
            }
          : null;

  // Pre-fill from the latest IG account + any prior OnboardingProfile. Either
  // side may be null — OnboardingChat skips whatever it already knows.
  const db = prismaForTenant(session.user.tenantId);
  const [ig, profile] = await Promise.all([
    db.instagramAccount.findFirst({
      orderBy: { createdAt: 'desc' },
      select: { handle: true, followerCount: true },
    }),
    db.onboardingProfile.findFirst({
      orderBy: { createdAt: 'desc' },
      select: {
        niche: true,
        subNiche: true,
        nicheDetail: true,
        targetAudience: true,
        brandVoice: true,
        contentStyle: true,
        currentFollowers: true,
        targetFollowers: true,
      },
    }),
  ]);

  const initial: OnboardingChatInitial = {
    instagramHandle: ig?.handle ?? undefined,
    currentFollowers: profile?.currentFollowers ?? ig?.followerCount ?? undefined,
    targetFollowers: profile?.targetFollowers ?? undefined,
    niche: profile?.niche ?? undefined,
    nicheLabel: profile?.contentStyle ?? undefined,
    nicheDetail: profile?.nicheDetail ?? profile?.subNiche ?? undefined,
    targetAudience: profile?.targetAudience ?? undefined,
    brandVoice: profile?.brandVoice ?? undefined,
  };

  return (
    <div className="max-w-2xl mx-auto py-8">
      {acctBanner && (
        <div
          className="card"
          style={{
            marginBottom: 12,
            padding: '14px 16px',
            background: acctBanner.accent
              ? 'color-mix(in oklch, var(--color-good, #10b981) 9%, var(--color-surface))'
              : 'color-mix(in oklch, var(--color-accent, #6366f1) 9%, var(--color-surface))',
            borderColor: acctBanner.accent
              ? 'var(--color-good, #10b981)'
              : 'var(--color-accent, #6366f1)',
            color: 'var(--color-ink)',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: 14 }}>✓ {acctBanner.title}</div>
          <div
            style={{ fontSize: 13, marginTop: 4, lineHeight: 1.5, color: 'var(--color-muted-foreground, inherit)' }}
          >
            {acctBanner.body}
          </div>
        </div>
      )}
      <OnboardingChat initial={initial} />
    </div>
  );
}
