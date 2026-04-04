/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: 'class',
    content: [
        './pages/**/*.{js,ts,jsx,tsx,mdx}',
        './components/**/*.{js,ts,jsx,tsx,mdx}',
        './app/**/*.{js,ts,jsx,tsx,mdx}',
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: [
                    'var(--font-sans)',
                    'var(--font-zh-serif)',
                    '"Source Han Serif SC"',
                    '"Source Han Serif CN"',
                    '"Noto Serif SC"',
                    '"Songti SC"',
                    '"STSong"',
                    'ui-sans-serif',
                    'system-ui',
                    'sans-serif',
                ],
                serif: [
                    'var(--font-serif)',
                    'var(--font-zh-serif)',
                    '"Source Han Serif SC"',
                    '"Source Han Serif CN"',
                    '"Noto Serif SC"',
                    '"Songti SC"',
                    '"STSong"',
                    'ui-serif',
                    'Georgia',
                    'serif',
                ],
            },
            colors: {
                background: 'var(--background)',
                foreground: 'var(--foreground)',
            },
        },
    },
    plugins: [],
}
