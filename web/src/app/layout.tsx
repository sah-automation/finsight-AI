import type { Metadata, Viewport } from 'next';

import { inter } from '@/lib/fonts';
import { messages } from '@/lib/messages';

import './globals.css';

export const metadata: Metadata = {
  title: {
    default: messages.productName,
    template: `%s · ${messages.productName}`,
  },
  description: messages.productDescription,
  applicationName: messages.productName,
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
