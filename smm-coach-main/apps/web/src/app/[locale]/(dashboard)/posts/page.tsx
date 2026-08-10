import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { getPostsData } from '@/lib/posts/data';
import { PostsView } from '@/components/traj/posts-view';

export const dynamic = 'force-dynamic';

export default async function PostsPage() {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');
  const data = await getPostsData(session.user.tenantId);
  // No connected Instagram account yet → nothing to list; the dashboard's
  // connect banner is the right place to start.
  if (!data) redirect('/dashboard');
  return <PostsView data={data} />;
}
