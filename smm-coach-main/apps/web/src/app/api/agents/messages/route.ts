import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const url = new URL(req.url);
  const limit = Math.min(100, parseInt(url.searchParams.get('limit') ?? '30', 10));

  const db = prismaForTenant(session.user.tenantId);
  const rows = await db.agentMessage.findMany({
    orderBy: { createdAt: 'desc' },
    take: limit,
  });
  const messages = rows.map((m) => ({
    id: m.id,
    agent: m.agent,
    role: m.role,
    content: m.content,
    important: m.important,
    createdAt: m.createdAt.toISOString(),
    minutesAgo: Math.max(0, Math.floor((Date.now() - m.createdAt.getTime()) / 60_000)),
  }));
  return NextResponse.json({ messages });
}
