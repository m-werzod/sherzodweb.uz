/**
 * GET /api/media/[...key]
 *
 * Streams an object from MinIO via the internal Docker DNS endpoint
 * (S3_ENDPOINT). Means we don't need to bind a public domain to the
 * minio container — the browser hits Next.js, Next.js hits MinIO,
 * Next.js streams the bytes back.
 *
 * Performance: piped through Node's `fetch` body — no full-buffer in
 * memory. Cache-Control: 7 days (objects are content-addressed, treated
 * as immutable).
 */
import type { NextRequest } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { getObject } from '@/lib/storage/s3';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ key: string[] }> },
): Promise<Response> {
  const { key: parts } = await ctx.params;
  const key = parts.map(decodeURIComponent).join('/');
  if (!key) return new Response('not found', { status: 404 });

  // Every media object is keyed `{tenantId}/...` (see media-mirror.ts,
  // pipeline.ts, upload-video, heygen). Without this gate the proxy streamed
  // ANY object by key — a leaked/shared URL gave login-less cross-tenant access
  // to private video/voice/IG media. Require a session and confirm the object's
  // tenant prefix matches the caller's tenant.
  const session = await auth();
  if (!session?.user?.tenantId) {
    return new Response('unauthorized', { status: 401 });
  }
  if (key.split('/')[0] !== session.user.tenantId) {
    return new Response('forbidden', { status: 403 });
  }

  try {
    // Honor Range so <video> can stream/seek (Safari/iOS refuse to play a 200
    // full-body response). S3 returns 206 + Content-Range when a Range is sent.
    const range = req.headers.get('range') ?? undefined;
    const out = await getObject(key, range);
    const body = out.Body;
    if (!body) return new Response('not found', { status: 404 });

    const isPartial = Boolean(range && out.ContentRange);
    const headers: Record<string, string> = {
      'Content-Type': out.ContentType ?? 'application/octet-stream',
      'Content-Length': out.ContentLength?.toString() ?? '',
      'Accept-Ranges': 'bytes', // advertise range support even on full responses
      'Cache-Control': 'public, max-age=604800, immutable',
      'ETag': out.ETag ?? '',
    };
    if (isPartial && out.ContentRange) headers['Content-Range'] = out.ContentRange;

    // Body is a Node ReadableStream — Response accepts it directly.
    return new Response(body as unknown as ReadableStream, {
      status: isPartial ? 206 : 200,
      headers,
    });
  } catch (err: unknown) {
    const code = (err as { name?: string }).name;
    if (code === 'NoSuchKey' || code === 'NotFound') {
      return new Response('not found', { status: 404 });
    }
    console.error('[media-proxy] failed', key, err);
    return new Response('media error', { status: 500 });
  }
}
