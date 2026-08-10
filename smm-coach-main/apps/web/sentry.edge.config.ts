/**
 * Sentry — edge runtime init (middleware, edge route handlers).
 * Soft-disabled when SENTRY_DSN is unset.
 */
import * as Sentry from '@sentry/nextjs';

const dsn = process.env.SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NODE_ENV ?? 'development',
    tracesSampleRate: 0,
  });
}
