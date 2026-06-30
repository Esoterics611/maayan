// Auth.js (NextAuth v5) — Credentials + role-based, JWT session strategy.
// Place at: auth.ts (project root) and re-export handlers in app/api/auth/[...nextauth]/route.ts
//
//   // app/api/auth/[...nextauth]/route.ts
//   export { GET, POST } from "@/auth";
//
// JWT strategy (not database sessions) because the Credentials provider doesn't
// play well with adapter-backed sessions. We carry `role` + `locale` in the token
// so route guards and server actions can authorize without a DB round-trip.

import NextAuth, { type DefaultSession } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { z } from "zod";
import bcrypt from "bcryptjs";
import { prisma } from "@/lib/db";
import type { Role, Locale } from "@prisma/client";

// Extend the session/JWT types with our custom claims.
declare module "next-auth" {
  interface Session {
    user: { id: string; role: Role; locale: Locale } & DefaultSession["user"];
  }
}
declare module "next-auth/jwt" {
  interface JWT {
    id: string;
    role: Role;
    locale: Locale;
  }
}

const credentialsSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

export const { handlers, signIn, signOut, auth } = NextAuth({
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  providers: [
    Credentials({
      credentials: { email: {}, password: {} },
      authorize: async (raw) => {
        const parsed = credentialsSchema.safeParse(raw);
        if (!parsed.success) return null;

        const { email, password } = parsed.data;
        const user = await prisma.user.findUnique({ where: { email } });
        if (!user?.passwordHash) return null;

        const ok = await bcrypt.compare(password, user.passwordHash);
        if (!ok) return null;

        // Returned object seeds the JWT (see callbacks below).
        return { id: user.id, email: user.email, name: user.name, role: user.role, locale: user.locale };
      },
    }),
  ],
  callbacks: {
    // Persist custom claims into the token on sign-in.
    jwt: ({ token, user }) => {
      if (user) {
        token.id = (user as { id: string }).id;
        token.role = (user as { role: Role }).role;
        token.locale = (user as { locale: Locale }).locale;
      }
      return token;
    },
    // Expose claims to the client/session.
    session: ({ session, token }) => {
      session.user.id = token.id;
      session.user.role = token.role;
      session.user.locale = token.locale;
      return session;
    },
  },
});

/** Throwing helper for server actions / route handlers. */
export async function requireUser() {
  const session = await auth();
  if (!session?.user) throw new Error("unauthenticated");
  return session.user;
}

/** Role gate for admin/instructor surfaces. */
export async function requireRole(...roles: Role[]) {
  const user = await requireUser();
  if (!roles.includes(user.role)) throw new Error("forbidden");
  return user;
}
