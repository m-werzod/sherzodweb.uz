import { redirect } from 'next/navigation';
import { headers } from 'next/headers';
import { prisma } from '@smm/db';
import { auth } from '@/lib/auth/auth';
import { isAdminEmail } from '@/lib/auth/admin';
import { getSidebarUser } from '@/lib/dashboard/sidebar-data';
import { getOnboardingState } from '@/lib/onboarding/state';
import { MobileShell } from '@/components/traj/mobile-shell';
import { PerformanceBanner } from '@/components/traj/performance-banner';
import { FloatingVoiceCoach } from '@/components/voice/floating-voice-coach';

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  // A 30-day JWT can outlive its DB row — orphan_cleanup deletes abandoned
  // tenants, leaving a "ghost session" whose tenantId no longer exists. Every
  // tenant-scoped query then renders empty and any write FK-violates. Detect
  // it once at the gate and bounce to a fresh sign-in instead.
  const tenantExists = await prisma.tenant.findUnique({
    where: { id: session.user.tenantId },
    select: { id: true },
  });
  if (!tenantExists) redirect('/sign-in?stale=1');

  // Universal "roadmap-not-ready" gate: redirect every dashboard page to the
  // onboarding flow until the active roadmap exists. The onboarding pages live
  // in their OWN route group ((onboarding)) so they're never rendered by this
  // layout — no exemption needed here. /admin is exempt so a platform admin can
  // always reach the panel even before finishing onboarding.
  const pathname = (await headers()).get('x-pathname') ?? '';
  const isGateExempt = /\/admin(\/|$)/.test(pathname);
  if (!isGateExempt) {
    const state = await getOnboardingState(session.user.tenantId);
    if (!state.onboardingDone) {
      // Fresh signup — never finished onboarding. Push them through it.
      redirect('/onboarding');
    }
    if (!state.roadmapReady) {
      // Onboarding done, AI still generating the roadmap. Keep the user on the
      // live narration page until the roadmap row flips to status='active'.
      redirect('/onboarding/loading');
    }
  }

  const sidebarUser = await getSidebarUser(session.user.tenantId, { name: session.user.name });
  const admin = isAdminEmail(session.user.email);

  return (
    <>
      <MobileShell user={sidebarUser} isAdmin={admin}>{children}</MobileShell>
      {/* Floating AI Inspector — every LLM call is logged + shown here. */}
      {/* Floating performance-review banner — shows only when the agent loop
          has an open pivot recommendation for this tenant (user approves the
          replan or dismisses). */}
      <PerformanceBanner />
      {/* Global floating voice coach — stays mounted across navigation so the
          conversation continues while it moves you around the site. Hidden on
          /agents (the full nebula studio lives there). */}
      <FloatingVoiceCoach />
    </>
  );
}
