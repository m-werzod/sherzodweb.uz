/** GET /api/admin/users — platform-admin: list every user across all tenants. */
import { NextResponse } from 'next/server';
import { getAdminSession } from '@/lib/auth/admin';
import { getAdminUsers } from '@/lib/admin/data';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const session = await getAdminSession();
  if (!session) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const users = await getAdminUsers();
  return NextResponse.json({ users });
}
