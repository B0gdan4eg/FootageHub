import type { Metadata } from "next";
import { LocalizedLandingPage } from "@/components/landing/localized-landing-page";

export const metadata: Metadata = {
  title: "Envato, Freepik & Motion Array Downloader Bot",
  description: "Download Envato Elements, Freepik, and Motion Array assets through FootageHub. Get 5 files free and access your downloads worldwide.",
  alternates: {
    canonical: "/en",
    languages: {
      ru: "/",
      en: "/en",
      "x-default": "/en",
    },
  },
  openGraph: {
    title: "Envato, Freepik & Motion Array Downloader Bot | FootageHub",
    description: "Download stock assets through FootageHub with fast delivery via Telegram and the web.",
    url: "/en",
    locale: "en_US",
    alternateLocale: ["ru_RU"],
  },
};

export default function EnglishLandingPage() {
  return <LocalizedLandingPage language="en" />;
}
