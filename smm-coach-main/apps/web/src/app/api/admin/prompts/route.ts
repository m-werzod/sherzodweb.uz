/**
 * Platform-admin AI prompt management.
 *   GET /api/admin/prompts        full agent catalog (provider, model, prompts)
 *   PUT /api/admin/prompts        { agentKey, content?, reset? } — save/reset an override
 *
 * Writes the override to prompt_overrides (read by the agents' resolve_prompt),
 * then purges the agents' in-process cache so the change applies immediately.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { prisma } from '@smm/db';
import { getAdminSession } from '@/lib/auth/admin';
import { getAgentCatalog, purgePromptCache } from '@/lib/agents/client';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const session = await getAdminSession();
  if (!session) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  try {
    const agents = await getAgentCatalog();
    return NextResponse.json({ agents });
  } catch (e) {
    return NextResponse.json(
      { error: 'agents_unreachable', detail: String(e).slice(0, 200) },
      { status: 502 },
    );
  }
}

const PutSchema = z.object({
  agentKey: z.string().min(1).max(64),
  content: z.string().max(20000).optional(),
  reset: z.boolean().optional(),
});

export async function PUT(req: Request) {
  const session = await getAdminSession();
  if (!session) return NextResponse.json({ error: 'forbidden' }, { status: 403 });

  const parsed = PutSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid_body' }, { status: 400 });
  }
  const { agentKey, content, reset } = parsed.data;
  const editor = session.user!.email!;

  if (reset) {
    // Revert to the code default by removing the override row.
    await prisma.promptOverride.deleteMany({ where: { agentKey } });
  } else {
    if (!content || content.trim().length === 0) {
      return NextResponse.json({ error: 'empty_content' }, { status: 400 });
    }
    await prisma.promptOverride.upsert({
      where: { agentKey },
      create: { agentKey, content, enabled: true, updatedBy: editor },
      update: { content, enabled: true, updatedBy: editor },
    });
  }

  await purgePromptCache(agentKey);
  return NextResponse.json({ ok: true });
}
