/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['three'],

  serverExternalPackages: ['nodemailer'],

  // Disable the dev toolbar that causes "Failed to fetch" errors in Next.js 15
  devIndicators: false,

  images: {
    formats: ['image/avif', 'image/webp'],
    minimumCacheTTL: 86400,
    deviceSizes: [640, 750, 828, 1080, 1200, 1920],
    imageSizes: [16, 32, 48, 64, 96, 128, 256],
    remotePatterns: [
      { protocol: 'https', hostname: 'cdn-icons-png.flaticon.com' },
      { protocol: 'https', hostname: 'img.icons8.com' },
      { protocol: 'https', hostname: 'cdn.jsdelivr.net' },
    ],
  },

  // Compress responses
  compress: true,

  reactStrictMode: true,
}

module.exports = nextConfig
