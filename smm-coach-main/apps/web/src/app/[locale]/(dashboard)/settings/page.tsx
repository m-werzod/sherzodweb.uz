import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { getSettingsData } from '@/lib/settings/data';
import { SettingsView } from '@/components/traj/settings-view';
import { SpendPanel } from '@/components/traj/spend-panel';

export const dynamic = 'force-dynamic';

export default async function SettingsPage() {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  const data = await getSettingsData(session.user.tenantId, {
    name: session.user.name,
    email: session.user.email,
  });

  return (
    <>
      <SettingsView data={data} />
      <div style={{ marginTop: 22, maxWidth: 1100 }}>
        <SpendPanel />
      </div>
    </>
  );
}
