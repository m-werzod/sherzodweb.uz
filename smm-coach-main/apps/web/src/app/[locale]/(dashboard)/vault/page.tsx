import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { getVaultData } from '@/lib/vault/data';
import { VaultView } from '@/components/traj/vault-view';

export const dynamic = 'force-dynamic';

export default async function VaultPage() {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');
  const data = await getVaultData(session.user.tenantId);
  return <VaultView data={data} />;
}
