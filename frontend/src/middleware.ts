import { NextRequest, NextResponse } from "next/server";

const PROTECTED_ROUTES = ["/dashboard", "/download", "/ai", "/payment", "/admin"];
const AUTH_ROUTE = "/auth";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value;
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_ROUTES.some((route) => pathname.startsWith(route));

  // TEMP: disabled for preview
  // if (isProtected && !token) {
  //   const loginUrl = new URL(AUTH_ROUTE, request.url);
  //   loginUrl.searchParams.set("redirect", pathname);
  //   return NextResponse.redirect(loginUrl);
  // }

  if (pathname === AUTH_ROUTE && token) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/download/:path*", "/ai/:path*", "/payment/:path*", "/admin/:path*", "/auth"],
};
