/**
 * POST /api/client-error — browser crash reports → Telegram log channel.
 *
 * Fed by app/global-error.tsx (fire-and-forget). Unauthenticated by design (the error page may
 * render before/without a session), so it is hardened against abuse: same-origin check, tiny
 * body cap, and the shared notifyTelegramError dedupe (same message ≤1per 5 min) — a hot broken
 * page or a prankster becomes one line in the channel, not a flood.
 */
import { NextResponse } from 'next/server';
import { notifyTelegramError } from '@/lib/telegram';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  // Same-origin only — the reporter is our own error page, never a cross-site caller.
  const origin = req.headers.get('origin') || req.headers.get('referer') || '';
  const host = req.headers.get('host') || '';
  if (origin && host && !origin.includes(host)) {
    return NextResponse.json({ ok: false }, { status: 403 });
  }
  let body: { message?: string; digest?: string; url?: string } = {};
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false }, { status: 400 });
  }
  const message = String(body.message || 'unknown').slice(0, 400);
  const context = [body.url && `URL: ${String(body.url).slice(0, 200)}`, body.digest && `digest: ${String(body.digest).slice(0, 60)}`]
    .filter(Boolean)
    .join('\n');
  notifyTelegramError('brauzer', new Error(message), context);
  return NextResponse.json({ ok: true });
}
