/**
 * Edit a content pillar's share % / color / perfScore. Used by the Settings
 * page so the user can rebalance pillars without re-running onboarding.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

const BodySchema = z.object({
  name: z.string().min(2).max(80).optional(),
  sharePct: z.number().int().min(0).max(100).optional(),
  color: z.string().max(20).nullable().optional(),
});

export async function PATCH(
  req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const { id } = await ctx.params;

  const body = await req.json().catch(() => null);
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'invalid_body', issues: parsed.error.issues },
      { status: 400 },
    );
  }

  const db = prismaForTenant(session.user.tenantId);
  const pillar = await db.contentPillar.findFirst({ where: { id } });
  if (!pillar) {
    return NextResponse.json({ error: 'pillar_not_found' }, { status: 404 });
  }

  const updated = await db.contentPillar.update({
    where: { id },
    data: {
      ...(parsed.data.name !== undefined ? { name: parsed.data.name } : {}),
      ...(parsed.data.sharePct !== undefined ? { sharePct: parsed.data.sharePct } : {}),
      ...(parsed.data.color !== undefined ? { color: parsed.data.color } : {}),
    },
  });

  return NextResponse.json({ ok: true, pillar: updated });
}

export async function DELETE(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const { id } = await ctx.params;
  const db = prismaForTenant(session.user.tenantId);
  const pillar = await db.contentPillar.findFirst({ where: { id } });
  if (!pillar) {
    return NextResponse.json({ error: 'pillar_not_found' }, { status: 404 });
  }
  await db.contentPillar.delete({ where: { id } });
  return NextResponse.json({ ok: true });
}
