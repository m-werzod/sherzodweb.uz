import { redirect } from 'next/navigation';
import { prisma } from '@smm/db';
import { auth } from '@/lib/auth/auth';
import { OnboardingChrome } from '@/components/onboarding/onboarding-chrome';

/**
 * Onboarding/setup shell — its OWN route group (separate from (dashboard)) so
 * the sidebar-less "HISOBNI SOZLASH" chrome is decided by WHICH layout renders,
 * not a conditional inside a shared layout. (A shared layout doesn't re-render
 * on client navigation between /onboarding/loading and /dashboard, which left
 * the dashboard wearing the onboarding chrome with no sidebar.)
 *
 * No roadmap-ready gate here — these pages ARE the gate's destination.
 */
export default async function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  // Ghost-session guard: a 30-day JWT can outlive an orphan-cleaned tenant.
  const tenantExists = await prisma.tenant.findUnique({
    where: { id: session.user.tenantId },
    select: { id: true },
  });
  if (!tenantExists) redirect('/sign-in?stale=1');

  return (
    <>
      <OnboardingChrome>{children}</OnboardingChrome>
    </>
  );
}
