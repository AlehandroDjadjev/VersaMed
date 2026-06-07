import type { Metadata } from "next";
import { Fraunces, Sora } from "next/font/google";

import { AppChrome } from "@/components/app-chrome";
import { Providers } from "@/components/providers";
import "./globals.css";

const sora = Sora({
  variable: "--font-versa-sans",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-versa-display",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VersaMed",
  description: "Secure account access for the VersaMed platform.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sora.variable} ${fraunces.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <Providers>
          <div className="app-stage">
            <div className="ambient-orb ambient-orb-one" />
            <div className="ambient-orb ambient-orb-two" />
            <div className="ambient-grid" />
            <div className="relative z-10 flex min-h-screen flex-col">
              <AppChrome />
              {children}
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
