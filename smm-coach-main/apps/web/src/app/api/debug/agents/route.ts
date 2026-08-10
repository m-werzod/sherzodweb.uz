/**
 * GET /api/debug/agents — diagnose the web → agents service link.
 *
 * Every AI action that "isn't working" (script regenerate, brief fill, roadmap
 * generation) goes through the same HMAC-signed call to apps/agents. This
 * endpoint pings the agents /health AND makes one real signed request, so you
 * can tell apart: agents-down vs HMAC-mismatch vs all-good — without digging
 * through Coolify logs.
 *
 * Session-required so it doesn't leak config to anonymous visitors.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { getProviderConfig } from '@/lib/agents/client';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const base = process.env.AGENTS_BASE_URL ?? 'http://localhost:8000';
  const hmacSet = Boolean(process.env.AGENTS_HMAC_SECRET);

  // 1. Liveness — /health is exempt from HMAC, so this isolates "is the agents
  //    container up + reachable" from "is the signature valid".
  let health: string;
  try {
    const r = await fetch(`${base}/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(8000),
    });
    health = r.ok ? `ok (${r.status})` : `non-200 (${r.status})`;
  } catch (e) {
    health = `unreachable: ${(e as Error).message.slice(0, 140)}`;
  }

  // 2. Signed round-trip — exercises the exact HMAC path content_review uses.
  let signedCall: string;
  try {
    const providers = await getProviderConfig();
    signedCall = `ok — ${providers.length} providers`;
  } catch (e) {
    signedCall = `FAILED: ${(e as Error).message.slice(0, 180)}`;
  }

  const issues: string[] = [];
  if (!process.env.AGENTS_BASE_URL) {
    issues.push('AGENTS_BASE_URL not set on web — using localhost fallback (wrong in prod).');
  }
  if (!hmacSet) issues.push('AGENTS_HMAC_SECRET not set on the web service.');
  if (health.startsWith('unreachable')) {
    issues.push(
      'Agents service unreachable — check AGENTS_BASE_URL and that the agents container is running in Coolify.',
    );
  }
  if (signedCall.startsWith('FAILED') && /401|unauthorized/i.test(signedCall)) {
    issues.push(
      'HMAC MISMATCH (401): AGENTS_HMAC_SECRET differs between the web and agents Coolify services. Set the SAME value in BOTH, then redeploy both.',
    );
  }

  return NextResponse.json({
    ok: health.startsWith('ok') && signedCall.startsWith('ok'),
    agentsBaseUrl: base,
    hmacSecretSet: hmacSet,
    health,
    signedCall,
    issues,
    hint: 'Script regenerate, brief fill, and roadmap generation all use this same web→agents path. If signedCall FAILED with 401, the HMAC secrets differ between the two services.',
  });
}
