/**
 * POST /api/production/montage/[taskId]/render
 *
 * Render a HAND-EDITED EDL from the Studio. Creates a pending final_render row
 * with meta.editSource='manual' + meta.edl; the agents montage_worker renders it
 * via render_edl directly — NO caption_stylist, NO LLM (manual edits must never
 * be clobbered or cost tokens).
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { EdlSchema, validateInboundEdl } from '@smm/shared-types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(
  req: Request,
  ctx: { params: Promise<{ taskId: string }> },
) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const tenantId = session.user.tenantId;
  const { taskId } = await ctx.params;
  const db = prismaForTenant(tenantId);

  const task = await db.contentTask.findFirst({ where: { id: taskId } });
  if (!task) return NextResponse.json({ error: 'task_not_found' }, { status: 404 });

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'bad_json' }, { status: 400 });
  }
  const parsed = EdlSchema.safeParse((body as { edl?: unknown })?.edl ?? body);
  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid_edl', detail: parsed.error.issues.slice(0, 4) }, { status: 422 });
  }
  const edl = parsed.data;

  // Trust boundary — the edited EDL is now untrusted ffmpeg input.
  const check = validateInboundEdl(edl);
  if (!check.ok) {
    return NextResponse.json({ error: 'edl_rejected', detail: check.reason }, { status: 422 });
  }

  // Stale-base guard: the EDL's cuts only make sense against the clip it was
  // built from. If the user re-uploaded since, refuse rather than mis-cut.
  const upload = await db.taskMedia.findFirst({
    where: { taskId, kind: 'user_upload', objectKey: { not: null } },
    orderBy: { createdAt: 'desc' },
  });
  if (!upload?.objectKey) {
    return NextResponse.json({ error: 'no_upload' }, { status: 409 });
  }
  if (edl.source.upload_key && edl.source.upload_key !== upload.objectKey) {
    return NextResponse.json({ error: 'stale_base', detail: 'Klip o‘zgargan — tahrirlar eskirgan.' }, { status: 409 });
  }

  // Dedup: one pending manual render per task protects the concurrency-1 worker.
  const pending = await db.taskMedia.findFirst({
    where: { taskId, kind: 'final_render', status: { in: ['pending', 'processing'] } },
  });
  if (pending) {
    return NextResponse.json({ error: 'already_rendering' }, { status: 409 });
  }

  const baseRender = await db.taskMedia.findFirst({
    where: { taskId, kind: 'final_render', status: 'ready' },
    orderBy: { createdAt: 'desc' },
  });

  const render = await db.taskMedia.create({
    data: {
      taskId,
      tenantId,
      kind: 'final_render',
      provider: 'ffmpeg',
      status: 'pending',
      meta: { edl, editSource: 'manual', baseRenderId: baseRender?.id ?? null },
    },
  });

  return NextResponse.json({ ok: true, renderId: render.id });
}
