/**
 * POST /api/meta/deauthorize — Meta "Deauthorize" callback.
 *
 * Fires when a user removes our app from their Instagram/Facebook settings.
 * Unlike data-deletion this does NOT erase their content — it just revokes the
 * connection: clear the stored OAuth token and mark the account unverified so
 * the agents stop calling the Graph API on their behalf.
 *
 * Public endpoint — authenticated by the signed_request HMAC.
 */
import { NextResponse } from 'next/server';
import { prisma } from '@smm/db';
import { parseSignedRequest } from '@/lib/instagram/signed-request';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  const secret = process.env.INSTAGRAM_APP_SECRET;
  if (!secret) {
    return NextResponse.json({ error: 'missing app secret' }, { status: 500 });
  }

  const form = await req.formData().catch(() => null);
  const signed = form?.get('signed_request');
  const data = typeof signed === 'string' ? parseSignedRequest(signed, secret) : null;
  if (!data?.user_id) {
    return NextResponse.json({ error: 'invalid signed_request' }, { status: 400 });
  }

  try {
    await prisma.instagramAccount.updateMany({
      where: { instagramUserId: String(data.user_id) },
      data: {
        oauthAccessTokenEnc: null,
        oauthExpiresAt: null,
        oauthScopes: [],
        verified: false,
      },
    });
  } catch (e) {
    console.error('[meta-deauthorize] failed', e);
  }

  return NextResponse.json({ ok: true });
}
