import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './globals.css';

export const metadata: Metadata = {
  title: 'Product Recommendation Prototype',
  description: 'JSON-backed enterprise product recommendation prototype.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  // Render a minimal app shell so the main page owns the product workflow UI.
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
