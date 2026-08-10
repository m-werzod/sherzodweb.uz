import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { getLeadsData } from '@/lib/leads/data';
import { LeadsView } from '@/components/traj/leads-view';

export const dynamic = 'force-dynamic';

export default async function LeadsPage() {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');
  const data = await getLeadsData(session.user.tenantId);
  return <LeadsView data={data} />;
}
