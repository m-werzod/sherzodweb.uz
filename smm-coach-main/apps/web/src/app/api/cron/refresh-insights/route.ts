/**
 * POST /api/cron/refresh-insights — refresh OFFICIAL per-post metrics for recently
 * published tasks via the Instagram Graph insights edge (reach/views/saved/shares)
 * + like/comment counts, and write them to ContentTask.actualMetrics.
 *
 * Session-less: authorized by x-cron-secret (the caller is the agents
 * insights_scheduler worker). This replaces the datacenter-IP-blocked instagrapi
 * scraper as the source of own-post actual metrics — only the web app holds the
 * per-account OAuth token + uses graph.instagram.com, so the official fetch lives
 * here. account_tracker (agents) then reads the populated actualMetrics.
 *
 * Needs the NUMERIC media id (ContentTask.instagramMediaId), captured at publish —
 * the shortcode in instagramPostId can't query /{media-id}/insights.
 */
import { timingSafeEqual } from 'node:crypto';
import { NextResponse } from 'next/server';
import { prisma } from '@smm/db';
import { fetchMediaCounts, fetchMediaInsights } from '@/lib/instagram/graph-api-client';
import { decryptToken } from '@/lib/security/crypto';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 300;

const WINDOW_DAYS = 14;
const BATCH = 50;

function authorized(req: Request): boolean {
  const secret = process.env.CRON_SECRET || process.env.AGENTS_HMAC_SECRET || '';
  const given = req.headers.get('x-cron-secret') ?? '';
  if (!secret || !given) return false;
  const a = Buffer.from(secret);
  const b = Buffer.from(given);
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function POST(req: Request) {
  if (!authorized(req)) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const since = new Date(Date.now() - WINDOW_DAYS * 24 * 60 * 60 * 1000);
  const tasks = await prisma.contentTask.findMany({
    where: {
      status: 'published',
      instagramMediaId: { not: null },
      publishedAt: { gte: since },
    },
    orderBy: { publishedAt: 'desc' },
    take: BATCH,
    select: {
      id: true,
      tenantId: true,
      instagramMediaId: true,
      roadmap: { select: { instagramAccount: { select: { oauthAccessTokenEnc: true } } } },
    },
  });

  let refreshed = 0;
  let skipped = 0;
  for (const t of tasks) {
    const enc = t.roadmap?.instagramAccount?.oauthAccessTokenEnc;
    const mediaId = t.instagramMediaId;
    if (!enc || !mediaId) {
      skipped += 1;
      continue;
    }
    let token: string;
    try {
      token = decryptToken(enc);
    } catch {
      skipped += 1;
      continue;
    }

    // Two official GETs: insights (reach/views/saved/shares) + counts (likes/comments).
    // Both swallow non-200 → {} so a single bad media never throws.
    const [ins, cnt] = await Promise.all([
      fetchMediaInsights(mediaId, token),
      fetchMediaCounts(mediaId, token),
    ]);

    const views = ins.views ?? 0;
    const likes = cnt.like_count ?? 0;
    const comments = cnt.comments_count ?? 0;
    const reach = ins.reach ?? 0;

    // Don't clobber existing metrics with an all-zero result from a transient
    // failure — only write when the API actually returned something.
    if (reach <= 0 && views <= 0 && likes <= 0 && comments <= 0) {
      skipped += 1;
      continue;
    }

    const actualMetrics = {
      likes,
      comments,
      views,
      plays: views, // the task-brief UI reads `plays`; views is the post-2025 metric
      reach,
      saves: ins.saved ?? 0, // detectors.compute_rates reads `saves`
      shares: ins.shares ?? 0,
    };

    await prisma.contentTask.update({
      where: { id: t.id },
      data: { actualMetrics },
    });
    refreshed += 1;
  }

  return NextResponse.json({ ok: true, scanned: tasks.length, refreshed, skipped });
}
