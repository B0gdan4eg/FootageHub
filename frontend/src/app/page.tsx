import type { Metadata } from "next";
import { LocalizedLandingPage } from "@/components/landing/localized-landing-page";

export const metadata: Metadata = {
  title: "Скачать Envato, Freepik и Motion Array",
  description: "Скачивайте файлы с Envato Elements, Freepik и Motion Array через FootageHub. Первые 5 файлов бесплатно.",
  alternates: {
    canonical: "/",
    languages: {
      ru: "/",
      en: "/en",
      "x-default": "/en",
    },
  },
  openGraph: {
    title: "FootageHub — Envato, Freepik и Motion Array",
    description: "Премиум-файлы со стоковых платформ через Telegram и веб-интерфейс.",
    url: "/",
    locale: "ru_RU",
    alternateLocale: ["en_US"],
  },
};

export default function LandingPage() {
  return <LocalizedLandingPage language="ru" />;
}
