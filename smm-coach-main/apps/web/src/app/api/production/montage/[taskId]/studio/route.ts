/**
 * GET /api/production/montage/[taskId]/studio
 *
 * One-click "Studioga kirish": builds the STUDIO deep-link for this task
 * on-demand (fresh presigned clip + save token) and 302-redirects the browser
 * into the STUDIO editor. Falls back to the in-app per-task studio page when
 * STUDIO_URL isn't configured yet.
 */
import { headers } from 'next/headers';
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { buildStudioUrl, studioOrigin } from '@/lib/studio/link';
import { ensureStudioSourceMp4 } from '@/lib/agents/client';

export const dynamic = 'force-dynamic';
// Bounded wait for the async .mov→mp4 remux (it runs in the background now); far
// below the old 180s, and the clip route falls back to the raw upload if it isn't
// ready in time.
export const maxDuration = 30;

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ taskId: string }> },
) {
  // The PUBLIC origin of this app. Behind Coolify's proxy `_req.url` is the internal bind address
  // (e.g. 0.0.0.0:3000), so an absolute redirect built from it is unreachable in the browser
  // (ERR_ADDRESS_INVALID). Prefer the configured public URL, then the proxy's forwarded host.
  const h = await headers();
  const fwdHost = h.get('x-forwarded-host') || h.get('host') || '';
  const proto = h.get('x-forwarded-proto') || 'https';
  const appOrigin =
    process.env.NEXTAUTH_URL || (fwdHost ? `${proto}://${fwdHost}` : new URL(_req.url).origin);
  const inApp = (path: string) => NextResponse.redirect(new URL(path, appOrigin));

  const session = await auth();
  if (!session?.user?.tenantId) {
    return inApp('/sign-in');
  }
  const tenantId = session.user.tenantId;
  const { taskId } = await ctx.params;
  const db = prismaForTenant(tenantId);

  const task = await db.contentTask.findFirst({
    where: { id: taskId },
    select: { id: true, title: true },
  });
  if (!task) {
    return NextResponse.json({ error: 'task_not_found' }, { status: 404 });
  }

  // No raw clip uploaded yet → the external STUDIO would open EMPTY (a blank "new project"), which
  // is NOT the flow: the user must upload the clip they recorded so the AI auto-montages it. Send
  // them to the in-app per-task workspace, which shows the "Video yuklash" step (and, once a clip is
  // up, the AI's montage + a "Studio'da montaj" button to refine externally). This is also the
  // fallback when STUDIO isn't deployed. Must run BEFORE the (pointless-without-a-clip) remux.
  const upload = await db.taskMedia.findFirst({
    where: { taskId, kind: 'user_upload', objectKey: { not: null } },
    orderBy: { createdAt: 'desc' },
    select: { objectKey: true },
  });
  if (!upload?.objectKey || !studioOrigin()) {
    return inApp(`/production/${taskId}`);
  }

  // Kick off (or pick up) the async .mov→mp4 remux and wait BRIEFLY for it, so
  // STUDIO's Web Audio decode works (Chromium can't decodeAudioData a .mov →
  // silent no-audio export). The transcode runs in the agents background; we poll
  // its status up to ~21s (short H.264 clips finish in seconds via -c:v copy) and
  // redirect regardless — the clip route serves the raw upload if it isn't ready,
  // and an upload-time pre-warm means it's usually cached already.
  for (let i = 0; i < 7; i++) {
    try {
      const r = await ensureStudioSourceMp4(tenantId, taskId);
      if (r.status === 'ready' || r.status === 'passthrough') break;
    } catch (err) {
      console.error('[studio] source mp4 ensure failed', err);
      break;
    }
    await new Promise((res) => setTimeout(res, 3000));
  }

  const url = await buildStudioUrl({
    tenantId,
    taskId,
    uploadKey: upload.objectKey,
    name: task.title,
    origin: appOrigin,
  });
  if (!url) {
    return inApp(`/production/${taskId}`);
  }
  return NextResponse.redirect(url);
}
