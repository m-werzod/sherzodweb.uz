/**
 * GET /api/production/montage — the montage hub's live data, polled by the
 * Production Studio while any render is in flight.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { getMontageTasks } from '@/lib/production/data';

export const dynamic = 'force-dynamic';

export async function GET() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const tasks = await getMontageTasks(session.user.tenantId);
  return NextResponse.json({ tasks });
}
