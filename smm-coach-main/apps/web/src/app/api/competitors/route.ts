/**
 * GET    /api/competitors        → tenant's tracked competitors
 * POST   /api/competitors {handle} → add a competitor (probes initial followers)
 * DELETE /api/competitors?id=…    → stop tracking one
 *
 * Rows here are what `competitor_tracker` (apps/agents/app/workers/
 * competitor_tracker.py) refreshes every 12h. Before this endpoint the table
 * was always empty, so the worker logged `count=0` forever — now the user can
 * seed it. The worker only fetches real follower counts when IG_SCRAPER_ACCOUNTS
 * is configured; otherwise rows keep their last real value (no fabrication).
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { probeInstagramProfile } from '@/lib/agents/client';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const MAX_COMPETITORS = 10;

export async function GET() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const db = prismaForTenant(session.user.tenantId);
  const competitors = await db.competitorTrack.findMany({
    orderBy: { followers: 'desc' },
    select: {
      id: true,
      handle: true,
      followers: true,
      growthRate: true,
      overlapPct: true,
      lastScrapedAt: true,
    },
  });
  return NextResponse.json({ competitors });
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const body = (await req.json().catch(() => null)) as { handle?: string } | null;
  const handle = normalizeHandle(body?.handle ?? '');
  if (!handle) {
    return NextResponse.json({ error: 'invalid_handle' }, { status: 400 });
  }

  const db = prismaForTenant(session.user.tenantId);

  const count = await db.competitorTrack.count();
  if (count >= MAX_COMPETITORS) {
    return NextResponse.json(
      { error: 'limit_reached', message: `Eng ko'pi ${MAX_COMPETITORS} ta raqobatchi.` },
      { status: 409 },
    );
  }

  const existing = await db.competitorTrack.findFirst({ where: { handle } });
  if (existing) {
    return NextResponse.json({ error: 'already_tracked' }, { status: 409 });
  }

  // Best-effort initial follower count via the anonymous probe — the worker
  // will keep it fresh. A failed probe still creates the row (followers 0);
  // the worker fills it in on the next pass when scrapers are configured.
  let followers = 0;
  try {
    const probe = await probeInstagramProfile(handle);
    if (probe.ok) followers = probe.followers;
  } catch {
    /* probe is best-effort — row is created either way */
  }

  const created = await db.competitorTrack.create({
    data: {
      tenantId: session.user.tenantId,
      handle,
      followers,
      lastScrapedAt: followers > 0 ? new Date() : null,
    },
    select: { id: true, handle: true, followers: true, growthRate: true, overlapPct: true, lastScrapedAt: true },
  });
  return NextResponse.json({ competitor: created }, { status: 201 });
}

export async function DELETE(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const id = new URL(req.url).searchParams.get('id');
  if (!id) {
    return NextResponse.json({ error: 'missing_id' }, { status: 400 });
  }
  const db = prismaForTenant(session.user.tenantId);
  // deleteMany so the tenant-scope filter applies (a wrong id just deletes 0).
  await db.competitorTrack.deleteMany({ where: { id } });
  return NextResponse.json({ ok: true });
}

function normalizeHandle(raw: string): string | null {
  const h = raw
    .trim()
    .replace(/^@/, '')
    .replace(/^https?:\/\/(www\.)?instagram\.com\//i, '')
    .replace(/\/.*$/, '')
    .trim();
  // IG handles: letters, digits, period, underscore, 1-30 chars.
  if (!/^[A-Za-z0-9._]{1,30}$/.test(h)) return null;
  return h.toLowerCase();
}
