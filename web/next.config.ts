import type { NextConfig } from 'next';

// Keep the app portable by avoiding platform-specific Next.js settings.
const nextConfig: NextConfig = {
  allowedDevOrigins: ['127.0.0.1'],
  reactStrictMode: true,
};

export default nextConfig;
