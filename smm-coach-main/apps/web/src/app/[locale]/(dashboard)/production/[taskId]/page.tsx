import { notFound, redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { getMontageTask } from '@/lib/production/data';
import { higgsfieldConfigured as higgsfieldCredsPresent } from '@/lib/higgsfield/client';
import { TaskStudio } from '@/components/traj/task-studio';

export const dynamic = 'force-dynamic';

/** Per-task Production Studio — the rich montage workspace for one task.
 *  The "Studio'da montaj" button opens the STUDIO browser editor via the
 *  /api/production/montage/[taskId]/studio redirect route (on-demand deep-link). */
export default async function TaskStudioPage({
  params,
}: {
  params: Promise<{ taskId: string }>;
}) {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  const { taskId } = await params;
  const task = await getMontageTask(session.user.tenantId, taskId);
  if (!task) notFound();

  return (
    <TaskStudio
      task={task}
      userId={session.user.id}
      studioConfigured={Boolean(process.env.STUDIO_URL)}
      // Single gate (fixes split-brain): the flag AND the SAME creds the agents render uses.
      higgsfieldConfigured={process.env.ENABLE_HIGGSFIELD === 'true' && higgsfieldCredsPresent()}
      runwayConfigured={process.env.ENABLE_RUNWAY_RESTYLE === 'true' && Boolean(process.env.RUNWAY_API_KEY)}
    />
  );
}
