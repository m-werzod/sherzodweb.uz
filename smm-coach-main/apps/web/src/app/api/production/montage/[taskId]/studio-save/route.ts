/**
 * POST /api/production/montage/[taskId]/studio-save
 *
 * Receives the finished montage exported by STUDIO (the browser editor, a
 * separate origin) and saves it as the task's final_render. Authorized by the
 * short-lived HMAC token STUDIO was handed in its deep-link — NOT a session,
 * since STUDIO is cross-origin. No agents/ffmpeg: STUDIO already rendered it.
 */
import { NextResponse } from 'next/server';
import { prisma } from '@smm/db';
import { putObject, mediaUrl, deleteObject } from '@/lib/storage/s3';
import { STUDIO_CONTRACT_VERSION, parseStudioToken } from '@/lib/studio/link';
import { notifyTelegram } from '@/lib/telegram';
import { EdlSchema } from '@smm/shared-types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 60;

const MAX_BYTES = 300 * 1024 * 1024;

function cors(): Record<string, string> {
  const origin = process.env.STUDIO_URL || '*';
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'content-type',
  };
}

export function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: cors() });
}

export async function POST(
  req: Request,
  ctx: { params: Promise<{ taskId: string }> },
) {
  const { taskId } = await ctx.params;
  const headers = cors();

  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ error: 'bad_form' }, { status: 400, headers });
  }
  const token = String(form.get('token') ?? '');
  const parsed = parseStudioToken(token);
  if (!parsed.ok) {
    // Distinguish an EXPIRED token (long edit) so STUDIO can show a "re-open from
    // SMM" hint instead of a bare 401.
    const code = parsed.reason === 'expired' ? 'token_expired' : 'unauthorized';
    return NextResponse.json({ error: code }, { status: 401, headers });
  }
  const claim = parsed;
  if (claim.taskId !== taskId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401, headers });
  }
  // Reject a token whose EXPLICIT wire-contract version we don't recognize (a
  // web↔STUDIO param/field contract change) with a clear code — not a confusing
  // 401. Pre-versioning tokens have no `v` and are accepted (graceful).
  if (claim.v != null && claim.v !== STUDIO_CONTRACT_VERSION) {
    return NextResponse.json({ error: 'contract_mismatch' }, { status: 409, headers });
  }

  const file = form.get('file');
  if (!(file instanceof Blob)) {
    return NextResponse.json({ error: 'no_file' }, { status: 400, headers });
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json({ error: 'too_large' }, { status: 413, headers });
  }

  // Optional EDL write-back: STUDIO serializes its edited timeline (edlFromProject) and posts it
  // so we persist the edited EDL (re-open into STUDIO + server re-render) instead of only the MP4.
  // Validated; a malformed/absent EDL is ignored (the MP4 render stays authoritative), never a
  // hard failure — and priorMeta.edl (the AI draft) is kept in that case.
  let editedEdl: unknown;
  const edlRaw = form.get('edl');
  if (typeof edlRaw === 'string' && edlRaw) {
    try {
      const parsedEdl = EdlSchema.safeParse(JSON.parse(edlRaw));
      if (parsedEdl.success) editedEdl = parsedEdl.data;
    } catch {
      /* malformed JSON — ignore */
    }
  }

  // The token proves tenant ownership of this task — use raw prisma (no session
  // is available cross-origin) but stay scoped to the token's tenant + task.
  const task = await prisma.contentTask.findFirst({
    where: { id: taskId, tenantId: claim.tenantId },
    select: { id: true },
  });
  if (!task) {
    return NextResponse.json({ error: 'task_not_found' }, { status: 404, headers });
  }

  // Capture the superseded render's object(s) so we can reclaim them from MinIO
  // after the swap — the deleteMany below removes only the DB row; nothing else
  // GCs the orphaned object. The new key is timestamped, so it never collides.
  const priorRenders = await prisma.taskMedia.findMany({
    where: { taskId, tenantId: claim.tenantId, kind: 'final_render' },
    select: { objectKey: true, meta: true },
  });
  // Preserve the prior render's meta (AI draft `edl`, graded `normalizedKey`, `coverKey`) so that
  // after a STUDIO save, re-opening into STUDIO + /edl + /clip + the cover keep working. Without
  // this the swap dropped them: /edl 404'd, /clip fell back to the raw clip (losing the graded
  // base), and the cover was lost — undoing the graded-base + cover work.
  const priorMeta = (priorRenders.find((r) => r.meta && typeof r.meta === 'object' && !Array.isArray(r.meta))?.meta ?? {}) as Record<string, unknown>;

  const buffer = Buffer.from(await file.arrayBuffer());
  const objectKey = `${claim.tenantId}/${taskId}/studio-${Date.now()}.mp4`;

  try {
    // Upload OUTSIDE the DB transaction (the object store isn't transactional);
    // only after it succeeds do we swap the DB row, so a failed upload can never
    // delete the prior render and strand the task with nothing.
    await putObject({ key: objectKey, body: buffer, contentType: 'video/mp4' });

    // Atomic swap: delete the old final_render + insert the new one in ONE tx, so
    // a mid-failure (create throws after delete) can't leave the task with NO
    // render. deleteMany is tenant-scoped — destructive raw-prisma must carry
    // tenantId like every other media path (convention) even though the token
    // already proved ownership.
    const render = await prisma.$transaction(async (tx) => {
      await tx.taskMedia.deleteMany({
        where: { taskId, tenantId: claim.tenantId, kind: 'final_render' },
      });
      return tx.taskMedia.create({
        data: {
          taskId,
          tenantId: claim.tenantId,
          kind: 'final_render',
          provider: 'studio',
          status: 'ready',
          objectKey,
          url: mediaUrl(objectKey),
          contentType: 'video/mp4',
          sizeBytes: BigInt(buffer.length),
          costUsd: 0,
          meta: { ...priorMeta, ...(editedEdl ? { edl: editedEdl } : {}), editSource: 'studio' },
          completedAt: new Date(),
        },
      });
    });

    // Best-effort: now that the prior row is gone, reclaim its object so it
    // doesn't orphan in the bucket. Never let a cleanup failure fail the save.
    for (const p of priorRenders) {
      if (p.objectKey && p.objectKey !== objectKey) {
        await deleteObject(p.objectKey).catch(() => {});
      }
    }

    return NextResponse.json({ ok: true, renderId: render.id }, { headers });
  } catch (err) {
    // The object was uploaded OUTSIDE the tx; if the DB swap failed, delete it so
    // it doesn't orphan in the bucket (the prior render's row still points at its
    // own object, so this one is now unreferenced). Best-effort.
    await deleteObject(objectKey);
    // A silent failure here loses the user's finished montage with no operator
    // signal — alert (like heygen) + return a stable error STUDIO can surface.
    void notifyTelegram(
      `❌ STUDIO save xato · taskId=${taskId} · tenant=${claim.tenantId} · ${String(err).slice(0, 200)}`,
    );
    return NextResponse.json({ error: 'save_failed' }, { status: 500, headers });
  }
}
