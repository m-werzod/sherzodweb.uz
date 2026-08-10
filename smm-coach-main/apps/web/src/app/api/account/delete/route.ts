/**
 * POST /api/account/delete
 *
 * Permanently deletes the caller's ENTIRE tenant and all its data.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { deleteTenantCascade } from '@/lib/admin/data';

export async function POST() {
  const session = await auth();
  if (!session?.user?.id || !session.user.tenantId) {
    return NextResponse.json({ error: 'Avtorizatsiya talab qilinadi.' }, { status: 401 });
  }

  // Delete the WHOLE tenant + every tenant-scoped table (incl. the 6 FK-less ones
  // a bare tenant.delete would orphan) via the shared cascade helper — the same
  // path admin-delete and the Meta data-deletion callback use, so "all your data
  // is permanently deleted" is actually true. Scoped to the caller's OWN tenantId.
  await deleteTenantCascade(session.user.tenantId);

  return NextResponse.json({ message: "Hisob va barcha ma'lumotlar o'chirildi." }, { status: 200 });
}
