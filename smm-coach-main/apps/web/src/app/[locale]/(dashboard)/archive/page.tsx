import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { getArchiveData } from '@/lib/archive/data';
import { ArchiveView } from '@/components/traj/archive-view';

export const dynamic = 'force-dynamic';

export default async function ArchivePage() {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');
  const data = await getArchiveData(session.user.tenantId);
  return <ArchiveView data={data} />;
}
