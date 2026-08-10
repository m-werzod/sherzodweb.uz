/**
 * Sentry — browser-side init (page errors, unhandled promise rejections).
 * Soft-disabled when NEXT_PUBLIC_SENTRY_DSN is unset.
 */
import * as Sentry from '@sentry/nextjs';

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NODE_ENV ?? 'development',
    tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.05 : 0,
    replaysOnErrorSampleRate: 0,
    replaysSessionSampleRate: 0,
  });
}
