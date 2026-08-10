/**
 * PATCH /api/instagram/profile-audit/[itemId]
 *
 * Body: { action: 'done' | 'skip' | 'recheck' }
 *
 *   done    — user manually marks the item as fixed (works for fields the
 *             Graph API doesn't expose: highlights, contact button, link)
 *   skip    — user wants to ignore this suggestion
 *   recheck — re-fetch /me and auto-mark `done` if the rule says it's
 *             fixed (used for bio/name/profile_picture fields that we can
 *             observe via Graph API)
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { decryptToken } from '@/lib/security/crypto';
import { fetchProfile } from '@/lib/instagram/graph-api-client';
import { isItemFixed, type ProfileAudit } from '@/lib/instagram/profile-audit';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const Body = z.object({ action: z.enum(['done', 'skip', 'recheck']) });

export async function PATCH(
  req: Request,
  ctx: { params: Promise<{ itemId: string }> },
) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const { itemId } = await ctx.params;
  const body = await req.json().catch(() => null);
  const parsed = Body.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: 'invalid' }, { status: 400 });

  const db = prismaForTenant(session.user.tenantId);
  const ig = await db.instagramAccount.findFirst({ orderBy: { createdAt: 'desc' } });
  if (!ig?.profileAudit) {
    return NextResponse.json({ error: 'no_audit' }, { status: 404 });
  }

  const audit = ig.profileAudit as unknown as ProfileAudit;
  const item = audit.items.find((it) => it.id === itemId);
  if (!item) return NextResponse.json({ error: 'item_not_found' }, { status: 404 });

  const now = new Date().toISOString();
  let verified = false;

  if (parsed.data.action === 'done') {
    item.status = 'done';
    item.fixedAt = now;
  } else if (parsed.data.action === 'skip') {
    item.status = 'skipped';
  } else if (parsed.data.action === 'recheck') {
    // Re-fetch /me and apply the field-specific rule.
    if (!ig.oauthAccessTokenEnc) {
      return NextResponse.json({ error: 'no_oauth' }, { status: 400 });
    }
    // Rate limit: max 1 recheck per item per 30s. Stops a user spamming
    // the Graph API (and our budget) by hammering the button.
    const lastChecked = (item as { lastCheckedAt?: string }).lastCheckedAt;
    if (lastChecked && Date.now() - new Date(lastChecked).getTime() < 30_000) {
      return NextResponse.json(
        { error: 'rate_limited', message: '30 soniya kuting, keyin qayta tekshiring.' },
        { status: 429 },
      );
    }
    (item as { lastCheckedAt?: string }).lastCheckedAt = new Date().toISOString();
    try {
      const token = decryptToken(ig.oauthAccessTokenEnc);
      const profile = await fetchProfile(token);
      verified = isItemFixed(item, profile);
      if (verified) {
        item.status = 'done';
        item.fixedAt = now;
      }
      // Refresh cached profile too.
      await db.instagramAccount.update({
        where: { id: ig.id },
        data: {
          bio: profile.biography ?? ig.bio,
          avatarUrl: profile.profile_picture_url ?? ig.avatarUrl,
          followerCount: profile.followers_count ?? ig.followerCount,
          postsCount: profile.media_count ?? ig.postsCount,
          lastSyncedAt: new Date(),
        },
      });
    } catch (err) {
      console.error('[profile-audit] recheck failed:', err);
      return NextResponse.json({ error: 'recheck_failed' }, { status: 502 });
    }
  }

  await db.instagramAccount.update({
    where: { id: ig.id },
    data: { profileAudit: audit as never },
  });

  return NextResponse.json({
    item,
    verified,
    audit,
  });
}
