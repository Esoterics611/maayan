// Route guard. Place at: middleware.ts (project root).
// Protects /admin (ADMIN only) and /dashboard (any authenticated member).
// Uses the JWT from auth.ts — no DB hit on the edge.

import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const { nextUrl } = req;
  const user = req.auth?.user;
  const path = nextUrl.pathname;

  const needsAuth = path.startsWith("/dashboard") || path.startsWith("/admin");
  if (needsAuth && !user) {
    const login = new URL("/login", nextUrl);
    login.searchParams.set("callbackUrl", path);
    return NextResponse.redirect(login);
  }

  if (path.startsWith("/admin") && user?.role !== "ADMIN") {
    return NextResponse.redirect(new URL("/dashboard", nextUrl));
  }

  return NextResponse.next();
});

// Only run middleware on guarded routes (skip static assets / public pages).
export const config = {
  matcher: ["/dashboard/:path*", "/admin/:path*"],
};
