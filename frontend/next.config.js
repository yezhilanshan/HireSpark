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
                source: '/backend-proxy/socket.io/:path*',
                destination: `${backendOrigin}/socket.io/:path*`,
            },
            {
                source: '/backend-proxy/api/assistant/:path*',
                destination: `${backendOrigin}/api/assistant/:path*`,
            },
            {
                source: '/backend-proxy/api/evaluation/:path*',
                destination: `${backendOrigin}/api/evaluation/:path*`,
            },
            {
                source: '/backend-proxy/api/growth-report/:path*',
                destination: `${backendOrigin}/api/growth-report/:path*`,
            },
            {
                source: '/backend-proxy/api/insights/:path*',
                destination: `${backendOrigin}/api/insights/:path*`,
            },
            {
                source: '/backend-proxy/api/interview/:path*',
                destination: `${backendOrigin}/api/interview/:path*`,
            },
            {
                source: '/backend-proxy/api/interviews/:path*',
                destination: `${backendOrigin}/api/interviews/:path*`,
            },
            {
                source: '/backend-proxy/api/prewarm/:path*',
                destination: `${backendOrigin}/api/prewarm/:path*`,
            },
            {
                source: '/backend-proxy/api/question-bank/:path*',
                destination: `${backendOrigin}/api/question-bank/:path*`,
            },
            {
                source: '/backend-proxy/api/report/:path*',
                destination: `${backendOrigin}/api/report/:path*`,
            },
            {
                source: '/backend-proxy/api/replay/:path*',
                destination: `${backendOrigin}/api/replay/:path*`,
            },
            {
                source: '/backend-proxy/api/resume/:path*',
                destination: `${backendOrigin}/api/resume/:path*`,
            },
            {
                source: '/backend-proxy/api/review/:path*',
                destination: `${backendOrigin}/api/review/:path*`,
            },
        ]
    },
}

module.exports = nextConfig
