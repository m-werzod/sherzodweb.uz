import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { generateCoversForTenant, thumbnailsEnabled } from '@/lib/media/pipeline';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/**
 * POST /api/archive/covers — kick off concept-cover generation (gpt-image-1
 * low) for this tenant's roadmap tasks that lack one. Fire-and-forget: the
 * covers fill into task_media over the next minute; the client reloads to see
 * them. Returns the number of tasks queued.
 */
export async function POST() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  if (!thumbnailsEnabled()) {
    return NextResponse.json({ ok: false, reason: 'thumbnails_disabled' }, { status: 200 });
  }
  const started = await generateCoversForTenant(session.user.tenantId);
  return NextResponse.json({ ok: true, started });
}
