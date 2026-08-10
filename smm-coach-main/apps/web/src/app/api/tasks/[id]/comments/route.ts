/**
 * GET /api/tasks/[id]/comments — the comments on a task's published Instagram
 * post, fetched via the Graph API so the ids are repliable (instagrapi pks are a
 * different id space). Resolves the post's media id from its shortcode.
 *
 * Returns { connected, comments } — comment TEXT requires the app to be in Live
 * mode + instagram_business_manage_comments (Active under Standard Access for the
 * owner's own account).
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { decryptToken } from '@/lib/security/crypto';
import { fetchComments, fetchMedia } from '@/lib/instagram/graph-api-client';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const { id } = await ctx.params;
  const db = prismaForTenant(session.user.tenantId);

  const task = await db.contentTask.findFirst({
    where: { id },
    select: { instagramPostId: true, instagramPostUrl: true },
  });
  if (!task) return NextResponse.json({ error: 'task_not_found' }, { status: 404 });
  if (!task.instagramPostId) {
    return NextResponse.json({ connected: true, published: false, comments: [] });
  }

  const ig = await db.instagramAccount.findFirst({
    orderBy: { createdAt: 'desc' },
    select: { oauthAccessTokenEnc: true },
  });
  if (!ig?.oauthAccessTokenEnc) {
    return NextResponse.json({ connected: false, comments: [] });
  }

  try {
    const token = decryptToken(ig.oauthAccessTokenEnc);
    // Resolve the Graph media id from the stored shortcode (the post URL/shortcode
    // is what we persist; the comments edge needs the numeric media id). Compare
    // the EXACT shortcode segment, not a substring (a short code can be a prefix
    // of a longer one).
    const shortcode = task.instagramPostId;
    const codeOf = (permalink?: string): string | null =>
      permalink?.match(/instagram\.com\/(?:p|reel|reels|tv)\/([A-Za-z0-9_-]+)/)?.[1] ?? null;
    const media = await fetchMedia(token, 50);
    const mine = media.find((m) => codeOf(m.permalink) === shortcode) ?? null;
    const mediaId = mine?.id ?? (/^\d+$/.test(shortcode) ? shortcode : null);
    if (!mediaId) {
      return NextResponse.json({ connected: true, published: true, comments: [], note: 'media_not_found' });
    }
    const comments = await fetchComments(token, mediaId, 50);
    return NextResponse.json({
      connected: true,
      published: true,
      mediaId,
      comments: comments.map((c) => ({
        id: c.id,
        text: c.text ?? '',
        username: c.username ?? '',
        timestamp: c.timestamp ?? null,
        likeCount: c.like_count ?? 0,
      })),
    });
  } catch (e) {
    return NextResponse.json({ connected: true, error: (e as Error).message.slice(0, 160), comments: [] });
  }
}
