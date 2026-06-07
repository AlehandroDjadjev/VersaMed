import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const sessionId = request.cookies.get("sessionid")?.value;
  const isAuthenticated = Boolean(sessionId);
  const { pathname, search } = request.nextUrl;
  const isGuestOnlyPath = pathname === "/login" || pathname.startsWith("/signup");

  if ((pathname.startsWith("/account") || pathname.startsWith("/doctor")) && !isAuthenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  if (isGuestOnlyPath && isAuthenticated) {
    return NextResponse.redirect(new URL("/account", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/account/:path*",
    "/doctor/:path*",
    "/login",
    "/signup",
    "/signup/:path*",
  ],
};
