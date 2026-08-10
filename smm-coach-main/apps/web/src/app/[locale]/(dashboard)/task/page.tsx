import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { findCurrentTaskId } from '@/lib/task/data';

export const dynamic = 'force-dynamic';

export default async function TaskRootPage() {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  const currentId = await findCurrentTaskId(session.user.tenantId);
  if (currentId) redirect(`/task/${currentId}`);
  redirect('/roadmap');
}
