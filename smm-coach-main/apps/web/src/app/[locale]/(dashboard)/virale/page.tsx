import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { getViraleData, type ViraleMode } from '@/lib/virale/data';
import { ViraleView } from '@/components/traj/virale-view';

export const dynamic = 'force-dynamic';

export default async function ViralePage({
  searchParams,
}: {
  searchParams?: Promise<{ filter?: string }>;
}) {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');
  const params = (await searchParams) ?? {};
  const mode: ViraleMode =
    params.filter === 'region' ||
    params.filter === 'global' ||
    params.filter === 'likes' ||
    params.filter === 'accounts'
      ? params.filter
      : 'niche';
  const data = await getViraleData(session.user.tenantId, mode);
  return <ViraleView data={data} />;
}
