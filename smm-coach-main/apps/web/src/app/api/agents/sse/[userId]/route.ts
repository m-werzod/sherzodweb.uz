/**
 * Streams SSE from apps/agents to the browser. The browser opens this URL;
 * we forward the HMAC-signed request to apps/agents and pipe its
 * `text/event-stream` body straight through.
 */
import { auth } from '@/lib/auth/auth';
import { createHmac } from 'node:crypto';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const BASE = process.env.AGENTS_BASE_URL ?? 'http://localhost:8000';
const SECRET = process.env.AGENTS_HMAC_SECRET ?? '';

export async function GET(
  req: Request,
  ctx: { params: Promise<{ userId: string }> },
) {
  const session = await auth();
  const { userId } = await ctx.params;
  if (!session?.user || session.user.id !== userId) {
    return new Response('unauthorized', { status: 401 });
  }

  const ts = Math.floor(Date.now() / 1000);
  const sig = createHmac('sha256', SECRET).update(`${ts}.`).digest('hex');

  // Forward the browser's abort signal: when the EventSource closes, the
  // upstream agents SSE connection (and its Redis subscription) is torn down
  // promptly instead of leaking until the next keepalive ping fails to write.
  let upstream: Response;
  try {
    upstream = await fetch(`${BASE}/v1/streams/${userId}`, {
      headers: {
        'x-smm-timestamp': String(ts),
        'x-smm-signature': sig,
      },
      cache: 'no-store',
      signal: req.signal,
    });
  } catch {
    // Agents unreachable or the request was aborted. Return 502 so the
    // client's onerror fires and its reconnect/backoff runs, instead of
    // piping a broken 200 stream the browser would hammer.
    return new Response('upstream_unavailable', { status: 502 });
  }

  if (!upstream.ok || !upstream.body) {
    return new Response('upstream_error', { status: 502 });
  }

  return new Response(upstream.body, {
    headers: {
      'content-type': 'text/event-stream',
      'cache-control': 'no-cache, no-transform',
      connection: 'keep-alive',
    },
  });
}
