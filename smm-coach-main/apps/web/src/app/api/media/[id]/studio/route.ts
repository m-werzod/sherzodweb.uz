/**
 * GET /api/media/[id]/studio — open a completed Higgsfield generation in STUDIO.
 *
 * Builds a STUDIO deep-link whose clip is the generated video's public CDN URL
 * (smm_clip), binding the save-back token to the generation's task so edits
 * round-trip. Falls back to the raw result URL when STUDIO_URL is unset, and to
 * the task page when the generation isn't ready.
 */
import { headers } from 'next/headers';
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { buildStudioUrl, signStudioToken, studioOrigin } from '@/lib/studio/link';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.redirect(new URL('/sign-in', req.url));
  }
  const { id } = await ctx.params;
  const db = prismaForTenant(session.user.tenantId);

  const gen = await db.mediaGeneration.findFirst({
    where: { id },
    select: { id: true, taskId: true, status: true, resultUrl: true },
  });
  if (!gen) return NextResponse.json({ error: 'not_found' }, { status: 404 });

  // Where to send the user when a STUDIO link can't be built — the task brief
  // (the panel renders the result <video> there). NEVER 302 to the external
  // resultUrl: that would be an open redirect to an attacker-influenced URL.
  const fallback = new URL(gen.taskId ? `/task/${gen.taskId}` : '/roadmap', req.url);

  if (gen.status !== 'completed' || !gen.resultUrl || !studioOrigin()) {
    return NextResponse.redirect(fallback);
  }

  const h = await headers();
  const host = h.get('host') ?? '';
  const proto = h.get('x-forwarded-proto') ?? 'https';
  const origin = `${proto}://${host}`;
  // One token binds both the save-back AND the clip-proxy fetch. smm_clip points
  // at our same-origin proxy (/api/media/[id]/clip) — the SMM server fetches the
  // Higgsfield CDN URL (no CORS server-side) and re-serves it with CORS allowing
  // STUDIO, so the import works regardless of Higgsfield's CDN CORS policy.
  // Save-back only when the generation is tied to a REAL task; otherwise STUDIO
  // opens the clip for edit/export with no (would-404) save-back.
  const token = signStudioToken(session.user.tenantId, gen.taskId ?? gen.id);
  const url = await buildStudioUrl({
    tenantId: session.user.tenantId,
    taskId: gen.taskId ?? gen.id,
    saveBack: Boolean(gen.taskId),
    token,
    clipUrl: `${origin}/api/media/${gen.id}/clip?token=${encodeURIComponent(token)}`,
    name: 'AI video',
    origin,
  });
  return NextResponse.redirect(url ?? fallback);
}
