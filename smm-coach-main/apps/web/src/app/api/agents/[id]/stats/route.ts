import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { getAgentsData } from '@/lib/agents/data';
import type { AgentKind } from '@/lib/agents/config';

export const dynamic = 'force-dynamic';

const VALID: AgentKind[] = ['market', 'industry', 'writer', 'audience'];

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const { id } = await ctx.params;
  if (!VALID.includes(id as AgentKind)) {
    return NextResponse.json({ error: 'unknown_agent' }, { status: 400 });
  }
  const data = await getAgentsData(session.user.tenantId);
  return NextResponse.json(data.stats[id as AgentKind]);
}
