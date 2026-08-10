import createMiddleware from 'next-intl/middleware';
import type { NextRequest } from 'next/server';
import { routing } from './i18n/routing';

const intlMiddleware = createMiddleware(routing);

export default function middleware(req: NextRequest) {
  const res = intlMiddleware(req);
  // Expose the request pathname to server components so the (dashboard)
  // layout can decide whether to enforce the "roadmap-ready" gate without
  // doing an additional roundtrip. next/headers doesn't expose the URL
  // natively, so we piggyback on a custom header.
  res.headers.set('x-pathname', req.nextUrl.pathname);
  return res;
}

export const config = {
  // Match every path except API, static assets, Next internals, and the
  // metadata file-convention routes (apple-icon, icon, sitemap, robots,
  // manifest). Those are rendered at the root without a locale prefix
  // and 404 if next-intl rewrites them to /uz/<route>.
  matcher: [
    '/((?!api|_next|_vercel|apple-icon|icon|sitemap|robots|manifest|.*\\..*).*)',
  ],
};
