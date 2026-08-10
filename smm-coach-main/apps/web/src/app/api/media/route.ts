/**
 * GET /api/media?taskId=... — list this tenant's recent media generations
 * (optionally filtered to one task). Drives the brief's "AI video" history.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const taskId = new URL(req.url).searchParams.get('taskId');
  const db = prismaForTenant(session.user.tenantId);
  const items = await db.mediaGeneration.findMany({
    where: { ...(taskId ? { taskId } : {}) },
    orderBy: { createdAt: 'desc' },
    take: 20,
    select: { id: true, kind: true, status: true, resultUrl: true, prompt: true, createdAt: true },
  });
  return NextResponse.json({ items });
}
