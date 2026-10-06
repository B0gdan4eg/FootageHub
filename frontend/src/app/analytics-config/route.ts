export const dynamic = "force-dynamic";
export function GET() {
  const ga4 = process.env.GA4_MEASUREMENT_ID || "";
  const posthog = process.env.POSTHOG_PROJECT_TOKEN || "";
  const host = process.env.POSTHOG_HOST || "https://eu.i.posthog.com";
  return Response.json({
    ga4: /^G-[A-Z0-9]+$/.test(ga4) ? ga4 : "",
    posthog: /^phc_[A-Za-z0-9_-]+$/.test(posthog) ? posthog : "",
    posthogHost: ["https://eu.i.posthog.com", "https://us.i.posthog.com"].includes(host) ? host : "https://eu.i.posthog.com",
  }, { headers: { "Cache-Control": "no-store", "X-Robots-Tag": "noindex" } });
}
