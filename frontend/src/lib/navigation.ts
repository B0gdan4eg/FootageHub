export function safeReturnPath(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\x00-\x1f]/.test(value)) return "/dashboard";
  try {
    const url = new URL(value, "https://footagehub.invalid");
    if (url.origin !== "https://footagehub.invalid" || !["/dashboard", "/payment", "/download", "/ai"].includes(url.pathname)) return "/dashboard";
    return url.pathname + url.search;
  } catch { return "/dashboard"; }
}
