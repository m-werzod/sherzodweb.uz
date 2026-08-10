/**
 * Next.js server-startup hook (runs once when the Node server boots, in both
 * dev and the standalone production server). We use it to bootstrap the admin
 * account so a known credentials login exists without OAuth/sign-up.
 *
 * Guarded to the Node.js runtime; the prisma-backed work is dynamically
 * imported so it never leaks into the edge bundle.
 */
export async function register() {
  // POSITIVE condition block (not an early `return`): for the Edge bundle Next
  // statically replaces NEXT_RUNTIME with 'edge', so this whole block — and the
  // node:crypto it transitively imports — is dead-code-eliminated. An early
  // `return` would leave the dynamic import in the traced graph and break the
  // edge build with "node:crypto is not handled".
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { bootstrapAdminUser } = await import('@/lib/auth/bootstrap-admin');
    await bootstrapAdminUser();

    // 100% failure visibility: process-level crashes also land in the Telegram channel.
    // CRITICAL: adding an uncaughtException listener CANCELS Node's default die-on-crash —
    // a corrupted process must NOT keep serving. Report, give the fetch 1.5s to flush,
    // then exit(1) so Coolify restarts a clean container (the pre-listener behavior).
    const { notifyTelegramError } = await import('@/lib/telegram');
    process.on('uncaughtException', (err) => {
      notifyTelegramError('uncaught', err);
      setTimeout(() => process.exit(1), 1500).unref();
    });
    // unhandledRejection is survivable — report only; Next/Node logging still applies.
    process.on('unhandledRejection', (reason) => notifyTelegramError('unhandled', reason));
  }
}

/**
 * Next.js 15 hook: fires for EVERY uncaught error in server rendering, route
 * handlers and server actions — the complete server-side error feed.
 */
export async function onRequestError(
  err: unknown,
  request: { path: string; method: string },
): Promise<void> {
  if (process.env.NEXT_RUNTIME !== 'nodejs') return;
  const { notifyTelegramError } = await import('@/lib/telegram');
  notifyTelegramError('server', err, `${request.method} ${request.path}`);
}
