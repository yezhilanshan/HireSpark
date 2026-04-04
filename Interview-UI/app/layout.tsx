import type {Metadata} from 'next';
import { Inter, Newsreader } from 'next/font/google';
import './globals.css';
import { CommandPalette } from '@/components/command-palette';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });
const newsreader = Newsreader({ subsets: ['latin'], variable: '--font-serif', style: ['normal', 'italic'] });

export const metadata: Metadata = {
  title: 'Aura | AI Interview Intelligence',
  description: 'Refine your narrative. Master your interview.',
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" className={`${inter.variable} ${newsreader.variable}`}>
      <body className="font-sans bg-[#FAF9F6] text-[#1A1A1A] antialiased selection:bg-[#EBE9E0] selection:text-[#1A1A1A]" suppressHydrationWarning>
        {children}
        <CommandPalette />
      </body>
    </html>
  );
}
