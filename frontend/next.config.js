const trimTrailingSlash = (value = '') => value.replace(/\/+$/, '')

/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
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
}

module.exports = nextConfig
