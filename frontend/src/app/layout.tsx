import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { LanguageProvider } from "@/lib/language";
import { AnalyticsConsentBanner } from "@/components/analytics-consent";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://envato-freepik-download.store"),
  title: {
    default: "FootageHub",
    template: "%s | FootageHub",
  },
  description: "Download assets from Envato Elements, Freepik, and Motion Array with FootageHub.",
  openGraph: {
    siteName: "FootageHub",
    type: "website",
  },
  twitter: {
    card: "summary",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" data-theme="dark">
      <body
        data-ph-mask="true"
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <LanguageProvider>{children}<AnalyticsConsentBanner /></LanguageProvider>
      </body>
    </html>
  );
}
