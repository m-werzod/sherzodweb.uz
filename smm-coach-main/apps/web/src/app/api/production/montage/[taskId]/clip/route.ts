/**
 * GET /api/production/montage/[taskId]/clip?token=<studioToken>
 *
 * Streams the task's user-uploaded source clip to STUDIO (the browser editor,
 * a separate HTTPS origin). Authorized by the same short-lived HMAC token
 * STUDIO was handed in its deep-link — NOT a session (STUDIO is cross-origin).
 *
 * Why stream through the web app instead of a presigned MinIO URL: STUDIO is
 * served over HTTPS, MinIO's public endpoint is plain HTTP — the browser blocks
 * that mixed-content fetch. Proxying here keeps the clip URL on the same HTTPS
 * origin as the deep-link, and MinIO never needs a public domain.
 */
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { prisma } from '@smm/db';
import { getObject } from '@/lib/storage/s3';
import { verifyStudioToken } from '@/lib/studio/link';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

function cors(): Record<string, string> {
  const origin = process.env.STUDIO_URL || '*';
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'content-type',
  };
}

export function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: cors() });
}

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ taskId: string }> },
): Promise<Response> {
  const { taskId } = await ctx.params;
  const headers = cors();
  const token = req.nextUrl.searchParams.get('token') ?? '';
  const claim = verifyStudioToken(token);
  if (!claim || claim.taskId !== taskId) {
    return new Response('unauthorized', { status: 401, headers });
  }

  // The token proves tenant ownership of this task — raw prisma, scoped to the
  // token's tenant + task (no session is available cross-origin). Preference order:
  //  1. the render's normalized+GRADED base clip (matches the finished reel's look, already an
  //     mp4 with decodable audio) so STUDIO edits a source consistent with the render;
  //  2. the remuxed `studio_source` MP4 (browser-decodable audio);
  //  3. the raw upload (a .mov plays video but its audio won't Web-Audio-decode → silent export).
  const finalRender = await prisma.taskMedia.findFirst({
    where: { taskId, tenantId: claim.tenantId, kind: 'final_render', status: 'ready' },
    orderBy: { createdAt: 'desc' },
    select: { meta: true },
  });
  const normalizedKey = (finalRender?.meta as { normalizedKey?: string } | null)?.normalizedKey;
  const upload = normalizedKey
    ? { objectKey: normalizedKey, contentType: 'video/mp4' }
    : ((await prisma.taskMedia.findFirst({
        where: { taskId, tenantId: claim.tenantId, kind: 'studio_source', status: 'ready', objectKey: { not: null } },
        orderBy: { createdAt: 'desc' },
        select: { objectKey: true, contentType: true },
      })) ??
      (await prisma.taskMedia.findFirst({
        where: { taskId, tenantId: claim.tenantId, kind: 'user_upload', objectKey: { not: null } },
        orderBy: { createdAt: 'desc' },
        select: { objectKey: true, contentType: true },
      })));
  if (!upload?.objectKey) {
    return new Response('no_clip', { status: 404, headers });
  }

  try {
    const out = await getObject(upload.objectKey);
    const body = out.Body;
    if (!body) return new Response('not found', { status: 404, headers });
    return new Response(body as unknown as ReadableStream, {
      headers: {
        ...headers,
        'Content-Type': out.ContentType ?? upload.contentType ?? 'video/mp4',
        'Content-Length': out.ContentLength?.toString() ?? '',
        'Cache-Control': 'private, max-age=3600',
      },
    });
  } catch (err: unknown) {
    const code = (err as { name?: string }).name;
    if (code === 'NoSuchKey' || code === 'NotFound') {
      return new Response('not found', { status: 404, headers });
    }
    console.error('[studio-clip] failed', upload.objectKey, err);
    return new Response('clip error', { status: 500, headers });
  }
}
