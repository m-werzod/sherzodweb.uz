import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { getMontageTasks } from '@/lib/production/data';
import { ProductionStudio } from '@/components/traj/production-studio';

export const dynamic = 'force-dynamic';

/**
 * Production Studio — the real montage hub. Lists the tenant's montage-eligible
 * tasks with their renders + upload state, replacing the old mock studio.
 */
export default async function ProductionPage() {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  const tasks = await getMontageTasks(session.user.tenantId);
  return <ProductionStudio initial={tasks} userId={session.user.id} />;
}
