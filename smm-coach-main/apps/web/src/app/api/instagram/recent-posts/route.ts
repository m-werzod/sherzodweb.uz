import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { decryptToken } from '@/lib/security/crypto';
import { fetchMedia } from '@/lib/instagram/graph-api-client';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/**
 * GET /api/instagram/recent-posts — the user's latest IG media (fresh from the
 * Graph API, so it includes a just-published post). Powers the publish dialog's
 * "pick your post" grid so users don't hand-paste a URL (and mis-paste, which
 * silently breaks actual-metrics tracking). Returns [] when no OAuth token.
 */
export async function GET() {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const db = prismaForTenant(session.user.tenantId);
  const ig = await db.instagramAccount.findFirst({ orderBy: { createdAt: 'desc' } });
  if (!ig?.oauthAccessTokenEnc) return NextResponse.json({ posts: [] });

  let token: string;
  try {
    token = decryptToken(ig.oauthAccessTokenEnc);
  } catch {
    return NextResponse.json({ posts: [] });
  }

  try {
    const media = await fetchMedia(token, 12);
    const posts = media
      .map((m) => ({
        permalink: m.permalink ?? null,
        shortcode: m.permalink?.match(/\/(?:p|reel|reels|tv)\/([^/]+)/)?.[1] ?? null,
        thumbnailUrl: m.thumbnail_url ?? m.media_url ?? null,
        caption: (m.caption ?? '').slice(0, 80),
        mediaType: m.media_type,
      }))
      .filter((p) => p.permalink);
    return NextResponse.json({ posts });
  } catch (err) {
    return NextResponse.json({ posts: [], error: (err as Error).message.slice(0, 120) });
  }
}
