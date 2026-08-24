import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { Hero, StockMarquee } from "@/components/landing/hero";
import { HowItWorks, Sources, Pricing, Versus } from "@/components/landing/sections";
import { FAQ, CTA } from "@/components/landing/extras";
import type { LandingLanguage } from "@/components/landing/localized-content";

export function LocalizedLandingPage({ language }: { language: LandingLanguage }) {
  return (
    <div
      className="landing-page"
      data-no-translate
      data-page-language={language}
      lang={language}
      style={{ minHeight: "100vh", position: "relative" }}
    >
      <SiteHeader language={language} />
      <Hero language={language} />
      <StockMarquee />
      <HowItWorks language={language} />
      <Sources language={language} />
      <Versus language={language} />
      <Pricing language={language} />
      <FAQ language={language} />
      <CTA language={language} />
      <SiteFooter language={language} />
    </div>
  );
}
