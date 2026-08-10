/**
 * GET /api/production/montage/[taskId]/edl?token=<studioToken>
 *
 * Serves the task's AI-generated montage EDL (cuts/captions/overlays/motion) to STUDIO so it
 * opens with the AI DRAFT pre-loaded — the "AI-draft → human-refine" loop (G3) — instead of a
 * blank single-clip import. Authorized by the same short-lived HMAC token STUDIO carries in its
 * deep-link (NOT a session — STUDIO is a separate origin), exactly like the /clip route.
 *
 * The EDL lives in the latest final_render's meta.edl. Validated through EdlSchema before serving
 * so STUDIO always receives a canonical EDL (a 404 → STUDIO falls back to clip-only).
 */
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { prisma } from '@smm/db';
import { EdlSchema } from '@smm/shared-types';
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

  // The token proves tenant ownership — raw prisma scoped to the token's tenant + task (no
  // session cross-origin). The EDL is on the LATEST final_render's meta.edl.
  const render = await prisma.taskMedia.findFirst({
    where: { taskId, tenantId: claim.tenantId, kind: 'final_render' },
    orderBy: { createdAt: 'desc' },
    select: { meta: true },
  });
  const meta = render?.meta;
  const rawEdl =
    meta && typeof meta === 'object' && !Array.isArray(meta)
      ? (meta as Record<string, unknown>).edl
      : null;
  const parsed = rawEdl ? EdlSchema.safeParse(rawEdl) : null;
  if (!parsed || !parsed.success) {
    return new Response('no_edl', { status: 404, headers });
  }

  return new Response(JSON.stringify(parsed.data), {
    headers: { ...headers, 'Content-Type': 'application/json', 'Cache-Control': 'private, max-age=60' },
  });
}
