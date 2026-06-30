// Prisma client singleton. Place at: lib/db.ts
// Next.js dev hot-reload re-imports modules; without the global guard you'd open a
// new connection pool on every reload and exhaust Postgres. Standard pattern.

import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: process.env.NODE_ENV === "development" ? ["warn", "error"] : ["error"],
  });

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
