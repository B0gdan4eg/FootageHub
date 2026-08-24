import type { MetadataRoute } from "next";

const BASE_URL = "https://envato-freepik-download.store";

const languages = {
  ru: `${BASE_URL}/`,
  en: `${BASE_URL}/en`,
  "x-default": `${BASE_URL}/en`,
};

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: `${BASE_URL}/`,
      changeFrequency: "weekly",
      priority: 1,
      alternates: { languages },
    },
    {
      url: `${BASE_URL}/en`,
      changeFrequency: "weekly",
      priority: 1,
      alternates: { languages },
    },
  ];
}
