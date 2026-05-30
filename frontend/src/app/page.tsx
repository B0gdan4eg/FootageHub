"use client";

import { useState } from "react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { Hero, StockMarquee } from "@/components/landing/hero";
import { HowItWorks, Sources, Pricing, Versus } from "@/components/landing/sections";
import { SocialProof, FAQ, CTA } from "@/components/landing/extras";

export default function LandingPage() {
  const [currency, setCurrency] = useState<"rub" | "usd">("rub");

  return (
    <div style={{ minHeight: "100vh", position: "relative" }}>
      <SiteHeader />
      <Hero />
      <StockMarquee />
      <HowItWorks />
      <Sources />
      <SocialProof />
      <Versus />
      <Pricing currency={currency} setCurrency={setCurrency} />
      <FAQ />
      <CTA />
      <SiteFooter />
    </div>
  );
}
