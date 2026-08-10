import { redirect, notFound } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { getTaskBrief } from '@/lib/task/data';
import { TaskBriefView } from '@/components/traj/task-brief-view';

export const dynamic = 'force-dynamic';

export default async function TaskBriefPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  const { id } = await params;
  const task = await getTaskBrief(session.user.tenantId, id);
  if (!task) notFound();

  return <TaskBriefView task={task} />;
}
