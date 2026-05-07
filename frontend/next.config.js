const withBundleAnalyzer = require('@next/bundle-analyzer')({
    enabled: process.env.ANALYZE === 'true',
})

/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    images: {
        unoptimized: true,
    },
    experimental: {
        optimizePackageImports: [
            'lucide-react',
            'motion',
            'recharts',
        ],
    },
    webpack(config, { isServer }) {
        if (!isServer) {
            config.optimization.splitChunks = {
                chunks: 'all',
                cacheGroups: {
                    vendor: {
                        test: /[\\/]node_modules[\\/]/,
                        name: 'vendors',
                        chunks: 'all',
                    },
                    motion: {
                        test: /[\\/]node_modules[\\/]motion[\\/]/,
                        name: 'motion',
                        chunks: 'all',
                        priority: 10,
                    },
                    recharts: {
                        test: /[\\/]node_modules[\\/]recharts[\\/]/,
                        name: 'recharts',
                        chunks: 'all',
                        priority: 10,
                    },
                },
            }
        }
        return config
    },
}

module.exports = withBundleAnalyzer(nextConfig)
