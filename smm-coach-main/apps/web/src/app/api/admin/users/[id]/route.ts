/**
 * Platform-admin user management.
 *   PATCH /api/admin/users/[id]   { plan?, suspended?, monthlyBudgetUsd? }
 *   DELETE /api/admin/users/[id]  hard-delete the user (and their tenant if sole member)
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { prisma } from '@smm/db';
import { getAdminSession } from '@/lib/auth/admin';
import { deleteTenantCascade } from '@/lib/admin/data';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const PatchSchema = z.object({
  plan: z.enum(['free', 'pro', 'premium', 'enterprise']).optional(),
  suspended: z.boolean().optional(),
  // null clears the override (fall back to env default). Capped to a sane range.
  monthlyBudgetUsd: z.number().min(0).max(100000).nullable().optional(),
});

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await getAdminSession();
  if (!session) return NextResponse.json({ error: 'forbidden' }, { status: 403 });

  const { id } = await params;
  const parsed = PatchSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid_body', detail: parsed.error.format() }, { status: 400 });
  }
  const { plan, suspended, monthlyBudgetUsd } = parsed.data;

  const user = await prisma.user.findUnique({ where: { id }, select: { id: true, email: true, tenantId: true } });
  if (!user) return NextResponse.json({ error: 'not_found' }, { status: 404 });

  // Can't suspend yourself out of the admin panel.
  if (suspended === true && user.email === session.user!.email) {
    return NextResponse.json({ error: 'cannot_suspend_self' }, { status: 400 });
  }

  if (suspended !== undefined) {
    await prisma.user.update({
      where: { id },
      data: { suspendedAt: suspended ? new Date() : null },
    });
  }

  if (monthlyBudgetUsd !== undefined) {
    await prisma.tenant.update({
      where: { id: user.tenantId },
      data: { monthlyBudgetUsd },
    });
  }

  if (plan !== undefined) {
    const existing = await prisma.subscription.findFirst({
      where: { tenantId: user.tenantId },
      orderBy: { createdAt: 'desc' },
    });
    if (existing) {
      await prisma.subscription.update({
        where: { id: existing.id },
        data: { plan, status: 'active' },
      });
    } else {
      await prisma.subscription.create({
        data: { tenantId: user.tenantId, plan, provider: 'manual', status: 'active' },
      });
    }
  }

  return NextResponse.json({ ok: true });
}

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await getAdminSession();
  if (!session) return NextResponse.json({ error: 'forbidden' }, { status: 403 });

  const { id } = await params;
  const user = await prisma.user.findUnique({ where: { id }, select: { email: true, tenantId: true } });
  if (!user) return NextResponse.json({ error: 'not_found' }, { status: 404 });

  if (user.email === session.user!.email) {
    return NextResponse.json({ error: 'cannot_delete_self' }, { status: 400 });
  }

  const memberCount = await prisma.user.count({ where: { tenantId: user.tenantId } });
  if (memberCount <= 1) {
    // Sole member — delete the whole tenant and all its data.
    await deleteTenantCascade(user.tenantId);
    return NextResponse.json({ ok: true, deleted: 'tenant' });
  }
  // Multi-user tenant (B2B) — remove just this user.
  await prisma.user.delete({ where: { id } });
  return NextResponse.json({ ok: true, deleted: 'user' });
}
