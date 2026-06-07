import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const guestOnlyPaths = new Set(["/login", "/signup"]);

export function proxy(request: NextRequest) {
  const sessionId = request.cookies.get("sessionid")?.value;
  const isAuthenticated = Boolean(sessionId);
  const { pathname, search } = request.nextUrl;

  if (pathname.startsWith("/account") && !isAuthenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  if (guestOnlyPaths.has(pathname) && isAuthenticated) {
    return NextResponse.redirect(new URL("/account", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/account/:path*", "/login", "/signup"],
};
