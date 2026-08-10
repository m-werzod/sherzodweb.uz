/**
 * GET /api/media/[id]/clip?token=<studioToken>
 *
 * Streams a completed Higgsfield generation's clip to STUDIO (a separate HTTPS
 * origin). Authorized by the same short-lived HMAC token STUDIO got in its
 * deep-link — NOT a session (cross-origin).
 *
 * Why proxy instead of handing STUDIO the raw Higgsfield CDN URL: STUDIO fetches
 * the clip in-browser to decode it, so it's subject to the CDN's CORS policy
 * (which we don't control). The SMM SERVER fetching the CDN URL has no CORS
 * restriction, so we re-serve it on our own origin with CORS allowing STUDIO —
 * the import works regardless of Higgsfield's CORS headers.
 */
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { prismaForTenant } from '@smm/db';
import { verifyStudioToken } from '@/lib/studio/link';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

function cors(): Record<string, string> {
  return {
    'Access-Control-Allow-Origin': process.env.STUDIO_URL || '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'content-type',
  };
}

export function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: cors() });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await ctx.params;
  const headers = cors();
  const claim = verifyStudioToken(req.nextUrl.searchParams.get('token') ?? '');
  if (!claim) return new Response('unauthorized', { status: 401, headers });

  // The token proves tenant ownership; scope the lookup to it (no session
  // cross-origin). buildStudioUrl mints the token with (taskId ?? gen.id), so the
  // claim's taskId must match this generation's task (or its own id).
  const db = prismaForTenant(claim.tenantId);
  const gen = await db.mediaGeneration.findFirst({
    where: { id },
    select: { taskId: true, status: true, resultUrl: true },
  });
  if (!gen || claim.taskId !== (gen.taskId ?? id)) {
    return new Response('unauthorized', { status: 401, headers });
  }
  if (gen.status !== 'completed' || !gen.resultUrl) {
    return new Response('not_ready', { status: 404, headers });
  }

  try {
    const upstream = await fetch(gen.resultUrl);
    if (!upstream.ok || !upstream.body) {
      return new Response('upstream_error', { status: 502, headers });
    }
    return new Response(upstream.body, {
      headers: {
        ...headers,
        'Content-Type': upstream.headers.get('content-type') ?? 'video/mp4',
        'Cache-Control': 'private, max-age=3600',
      },
    });
  } catch (err) {
    console.error('[media-clip] stream failed', id, err);
    return new Response('clip_error', { status: 502, headers });
  }
}
