/**
 * POST /api/meta/data-deletion — Meta "Data Deletion Request" callback.
 *
 * Required for Instagram/Facebook App Review. When a user removes the app AND
 * requests data deletion (or via Meta's data deletion flow), Meta POSTs a
 * `signed_request` here. We verify it, delete ALL data tied to that Instagram
 * user, and return `{ url, confirmation_code }` so Meta can show the user a
 * status link — this exact JSON shape is mandated by Meta.
 *
 * Public endpoint (server-to-server from Meta) — auth is the signed_request
 * HMAC, not a session.
 */
import { NextResponse } from 'next/server';
import { randomBytes } from 'node:crypto';
import { prisma } from '@smm/db';
import { parseSignedRequest } from '@/lib/instagram/signed-request';
import { deleteTenantCascade } from '@/lib/admin/data';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function statusBase(reqUrl: string): string {
  return process.env.NEXTAUTH_URL || new URL(reqUrl).origin;
}

export async function POST(req: Request) {
  const secret = process.env.INSTAGRAM_APP_SECRET;
  if (!secret) {
    return NextResponse.json({ error: 'missing app secret' }, { status: 500 });
  }

  // Meta sends application/x-www-form-urlencoded: signed_request=<...>
  const form = await req.formData().catch(() => null);
  const signed = form?.get('signed_request');
  const data = typeof signed === 'string' ? parseSignedRequest(signed, secret) : null;
  if (!data?.user_id) {
    return NextResponse.json({ error: 'invalid signed_request' }, { status: 400 });
  }

  const code = randomBytes(8).toString('hex');

  // Delete everything tied to that Instagram user. The IG-scoped id maps to
  // InstagramAccount.instagramUserId → its tenant → full cascade delete.
  try {
    const acct = await prisma.instagramAccount.findUnique({
      where: { instagramUserId: String(data.user_id) },
      select: { tenantId: true },
    });
    if (acct) await deleteTenantCascade(acct.tenantId);
  } catch (e) {
    // Log but still return 200 with the receipt — Meta retries on non-200 and
    // a transient DB blip shouldn't look like a refusal to delete.
    console.error('[meta-data-deletion] delete failed', e);
  }

  return NextResponse.json({
    url: `${statusBase(req.url)}/data-deletion?code=${code}`,
    confirmation_code: code,
  });
}
