import { redirect } from 'next/navigation';
import { getAdminSession } from '@/lib/auth/admin';
import { getAdminUsers, getProviderOverview, getWorkerStatus } from '@/lib/admin/data';
import { getAgentCatalog, type AgentCatalogEntry } from '@/lib/agents/client';
import { AdminView } from '@/components/traj/admin-view';

export const dynamic = 'force-dynamic';

export default async function AdminPage() {
  const session = await getAdminSession();
  if (!session) redirect('/dashboard');

  // Agents service may be briefly unreachable — degrade to an empty catalog
  // rather than 500 the whole panel (users + providers still render).
  let agents: AgentCatalogEntry[] = [];
  let agentsError = false;
  const [users, providers, workers] = await Promise.all([
    getAdminUsers(),
    getProviderOverview(),
    getWorkerStatus(),
  ]);
  try {
    agents = await getAgentCatalog();
  } catch {
    agentsError = true;
  }

  return (
    <AdminView
      users={users}
      providers={providers}
      agents={agents}
      workers={workers}
      agentsError={agentsError}
      adminEmail={session.user!.email ?? ''}
    />
  );
}
