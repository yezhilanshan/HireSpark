const withBundleAnalyzer = require('@next/bundle-analyzer')({
    enabled: process.env.ANALYZE === 'true',
})

const trimTrailingSlash = (value = '') => value.replace(/\/+$/, '')

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
    async rewrites() {
        const backendOrigin = trimTrailingSlash(
            process.env.VERCEL_BACKEND_ORIGIN || process.env.BACKEND_ORIGIN || ''
        )

        if (!backendOrigin) {
            return []
        }

        return [
            {
                source: '/backend-proxy/:path*',
                destination: `${backendOrigin}/:path*`,
            },
        ]
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
