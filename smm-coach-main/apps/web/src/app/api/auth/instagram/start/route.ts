/**
 * GET /api/auth/instagram/start
 *
 * Kicks off the Instagram Business Login OAuth flow. Works in two
 * modes (decided by whether the visitor has an Auth.js session):
 *
 *   • signed in  → `connect` mode: link the IG account to the current
 *                  User+Tenant (existing behaviour)
 *   • not signed in → `signin` mode: callback creates a new User+Tenant
 *                  on first use, or signs in the existing user matched
 *                  by `InstagramAccount.instagramUserId`
 *
 * CSRF state and the chosen mode are stored in httpOnly cookies the
 * callback verifies.
 *
 * Optional `?return=/path` query passes the post-success landing.
 */
import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { randomBytes } from 'node:crypto';
import { auth } from '@/lib/auth/auth';
import { buildAuthorizeUrl } from '@/lib/instagram/graph-api-client';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const COOKIE_OPTS = {
  httpOnly: true as const,
  sameSite: 'lax' as const,
  secure: process.env.NODE_ENV === 'production',
  maxAge: 600,
  path: '/',
};

export async function GET(req: Request) {
  const session = await auth();
  const baseUrl = process.env.NEXTAUTH_URL || new URL(req.url).origin;
  const reqUrl = new URL(req.url);

  const mode: 'connect' | 'signin' = session?.user?.id ? 'connect' : 'signin';

  const state = randomBytes(16).toString('hex');
  const ret = reqUrl.searchParams.get('return') ?? (mode === 'signin' ? '/dashboard' : '/dashboard');
  const safeReturn = ret.startsWith('/') && !ret.startsWith('//') ? ret : '/dashboard';

  const jar = await cookies();
  jar.set('ig_oauth_state', state, COOKIE_OPTS);
  jar.set('ig_oauth_return', safeReturn, COOKIE_OPTS);
  jar.set('ig_oauth_mode', mode, COOKIE_OPTS);

  void baseUrl; // silence unused — kept in scope for future absolute-URL logging
  return NextResponse.redirect(buildAuthorizeUrl(state));
}
