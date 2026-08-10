/**
 * Sentry — server-side init (Next.js Route Handlers, Server Actions).
 * Soft-disabled when SENTRY_DSN is unset so dev/CI don't ping Sentry.
 */
import * as Sentry from '@sentry/nextjs';

const dsn = process.env.SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NODE_ENV ?? 'development',
    tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 0,
    // Strip /api/auth/* and /api/webhooks/* PII from error events
    beforeSend(event) {
      if (event.request?.cookies) delete event.request.cookies;
      if (event.request?.headers) {
        delete event.request.headers.cookie;
        delete event.request.headers.authorization;
      }
      return event;
    },
  });
}
