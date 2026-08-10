import type { NextConfig } from 'next';
import path from 'node:path';
import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: 'standalone',
  // Monorepo: trace from repo root so the standalone bundle picks up
  // workspace packages (@smm/db) and the Prisma engine binaries.
  outputFileTracingRoot: path.join(__dirname, '../../'),
  outputFileTracingIncludes: {
    '**/*': [
      '../../packages/db/generated/client/**/*',
      '../../packages/db/prisma/schema.prisma',
      '../../packages/db/prisma/migrations/**/*',
    ],
  },
  experimental: {
    typedRoutes: true,
    serverActions: { bodySizeLimit: '4mb' },
  },
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**.cdninstagram.com' },
      { protocol: 'https', hostname: '**.fbcdn.net' },
      { protocol: 'https', hostname: '**.r2.dev' },
      { protocol: 'https', hostname: '**.r2.cloudflarestorage.com' },
      // Demo / dev assets — strip these before production hardening.
      { protocol: 'https', hostname: 'api.dicebear.com' },
      { protocol: 'https', hostname: 'picsum.photos' },
      { protocol: 'https', hostname: 'fastly.picsum.photos' },
    ],
  },
  // Allow workspace packages to be imported directly without pre-build.
  transpilePackages: ['@smm/db', '@smm/shared-types'],
};

export default withNextIntl(config);
