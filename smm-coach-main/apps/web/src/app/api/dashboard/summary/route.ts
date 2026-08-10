import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { getDashboardData } from '@/lib/dashboard/data';

export const dynamic = 'force-dynamic';

export async function GET() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const data = await getDashboardData(session.user.tenantId, {
    name: session.user.name,
    locale: session.user.locale,
  });
  if (!data) {
    return NextResponse.json({ error: 'no_instagram_account' }, { status: 404 });
  }
  return NextResponse.json(data);
}
