import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
    ],
    // Enable image optimization
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    minimumCacheTTL: 60,
  },
  // Enable compression
  compress: true,
  // React strict mode for better performance
  reactStrictMode: true,
  // Enable experimental features for better performance
  experimental: {
    optimizeCss: true,
    // Tree-shake unused exports from these packages
    optimizePackageImports: ['framer-motion', 'lucide-react'],
  },
};

export default nextConfig;

