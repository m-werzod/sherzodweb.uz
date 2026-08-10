import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { OnboardingLoadingView } from '@/components/onboarding/loading-view';

export const dynamic = 'force-dynamic';

export default async function OnboardingLoadingPage({
  searchParams,
}: {
  searchParams: Promise<{ run?: string }>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect('/sign-in');

  const sp = await searchParams;
  return <OnboardingLoadingView userId={session.user.id} runId={sp.run ?? null} />;
}
