/**
 * PATCH /api/leads/[id] — update a lead's status / notes / draft reply.
 * Body: { status?, notes?, draftReply? }. Tenant-scoped via prismaForTenant
 * (the where clause gets tenantId injected, so a crafted id can't touch
 * another tenant's lead). Returns the updated lead.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';

const BodySchema = z.object({
  status: z.enum(['new', 'contacted', 'converted', 'dismissed']).optional(),
  notes: z.string().trim().max(2000).optional(),
  draftReply: z.string().trim().max(2000).optional(),
});

export async function PATCH(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const { id } = await ctx.params;
  const parsed = BodySchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success || Object.keys(parsed.data).length === 0) {
    return NextResponse.json({ error: 'invalid' }, { status: 400 });
  }

  const db = prismaForTenant(session.user.tenantId);
  try {
    const lead = await db.lead.update({
      where: { id },
      data: parsed.data,
      select: { id: true, status: true, notes: true, draftReply: true },
    });
    return NextResponse.json({ ok: true, lead });
  } catch {
    return NextResponse.json({ error: 'not_found' }, { status: 404 });
  }
}
