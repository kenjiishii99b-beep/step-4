/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config, { dev }) => {
    // Docker Desktop (Windows/Mac) のバインドマウント越しには inotify イベントが
    // 伝播しないため、ポーリング監視にフォールバックしてホットリロードを機能させる。
    if (dev) {
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
};

export default nextConfig;
