import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

const BodySchema = z.object({ done: z.boolean() });

export async function PATCH(
  req: Request,
  ctx: { params: Promise<{ id: string; itemId: string }> },
) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const { id, itemId } = await ctx.params;

  const body = await req.json().catch(() => null);
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid_body' }, { status: 400 });
  }

  const db = prismaForTenant(session.user.tenantId);

  // Confirm task ownership before mutating the checklist item.
  const task = await db.contentTask.findFirst({ where: { id } });
  if (!task) return NextResponse.json({ error: 'task_not_found' }, { status: 404 });

  await db.$executeRaw`
    UPDATE task_checklist_items
    SET done = ${parsed.data.done}, "updatedAt" = NOW()
    WHERE id = ${itemId} AND "taskId" = ${id}
  `;

  return NextResponse.json({ ok: true, done: parsed.data.done });
}
