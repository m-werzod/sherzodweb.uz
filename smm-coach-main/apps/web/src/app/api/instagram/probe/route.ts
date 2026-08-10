/**
 * GET /api/instagram/probe?handle=foo
 *
 * Calls the agents service's anonymous public profile probe. Used during
 * the signup wizard to surface real follower count without requiring an
 * Instagram OAuth flow. The wizard falls back to a manual input field
 * when `ok=false`.
 */
import { NextResponse } from 'next/server';
import { probeInstagramProfile } from '@/lib/agents/client';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(req: Request) {
  const url = new URL(req.url);
  const raw = url.searchParams.get('handle') ?? '';
  const handle = raw.trim().replace(/^@/, '');
  if (!handle || !/^[A-Za-z0-9._]{1,30}$/.test(handle)) {
    return NextResponse.json({ ok: false, error: 'invalid_handle' }, { status: 400 });
  }

  try {
    const probe = await probeInstagramProfile(handle);
    return NextResponse.json(probe);
  } catch (err) {
    // Don't 500 the wizard — surface ok:false so the UI can fall back to
    // manual input. Log via structured response so users can paste from
    // the browser network panel if they hit issues.
    return NextResponse.json(
      {
        ok: false,
        handle,
        followers: 0,
        following: 0,
        posts: 0,
        bio: null,
        avatarUrl: null,
        isPrivate: false,
        error: err instanceof Error ? err.message.slice(0, 200) : 'probe_failed',
      },
      { status: 200 },
    );
  }
}
