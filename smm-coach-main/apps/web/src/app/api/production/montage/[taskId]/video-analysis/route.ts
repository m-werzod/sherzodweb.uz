/**
 * POST /api/production/montage/[taskId]/video-analysis — deep video critique.
 *
 * Triggers the agents' Gemini-Files-API critique of the task's uploaded clip and returns the
 * structured VideoCritique (also persisted agent-side to the upload's meta.videoCritique, so the
 * task page shows it cached on next load). SYNCHRONOUS + slow (~2 min: download + 720p proxy +
 * Files API + Gemini), which is why this lives behind an explicit "Videoni tahlil qil" button
 * with a loading state rather than running on every page view.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { critiqueVideo } from '@/lib/agents/client';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 200; // self-hosted Node ignores this, but documents the ~2min budget

export async function POST(
  _req: Request,
  ctx: { params: Promise<{ taskId: string }> },
): Promise<Response> {
  const session = await auth();
  const tenantId = session?.user?.tenantId;
  if (!tenantId) return NextResponse.json({ ok: false, error: 'unauthorized' }, { status: 401 });

  const { taskId } = await ctx.params;
  // Tenant-scope guard: the task must belong to this tenant.
  const task = await prismaForTenant(tenantId).contentTask.findFirst({
    where: { id: taskId },
    select: { id: true },
  });
  if (!task) return NextResponse.json({ ok: false, error: 'not_found' }, { status: 404 });

  try {
    const res = await critiqueVideo(tenantId, taskId, session?.user?.id);
    return NextResponse.json(res);
  } catch {
    // Best-effort: a transient agents/Gemini failure shouldn't 500 the page.
    return NextResponse.json({ ok: false, error: "Tahlil xatosi — qayta urinib ko'ring." });
  }
}
