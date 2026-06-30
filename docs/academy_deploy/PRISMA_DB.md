# Prisma + Postgres: connection & the capacity-safe booking transaction

This is the part that bites you in production. Two concerns:

1. **Connection strings** differ between a long-lived server (Oracle VPS / Railway)
   and serverless (Vercel). Get this wrong and you exhaust Postgres connections.
2. **Capacity-limited booking** must be race-safe. Two parents clicking "book the
   last seat" at the same millisecond must not both succeed.

---

## 1. Connection strings

Keep `DATABASE_URL` as the single switch (same discipline as the RAG's
`GENERATION_BACKEND`). Only this value changes between hosts.

| Host | `DATABASE_URL` | Why |
|---|---|---|
| **Local dev** | `postgresql://academy:dev@localhost:5432/maavar?schema=public` | Postgres in Docker — matches prod, no SQLite drift. |
| **Oracle VPS / Railway / Render** (long-lived Node) | direct connection, e.g. `postgres://...@postgres:5432/maavar` | One process, pooled in-app by Prisma. |
| **Vercel (serverless)** | Neon **pooled** URL: `postgres://...-pooler.neon.tech/maavar?sslmode=require&pgbouncer=true&connection_limit=1` | Each invocation is its own process; without the pooler you'll blow past Postgres `max_connections`. |

For Vercel + Neon, also keep a non-pooled `DIRECT_URL` for migrations:

```prisma
// schema.prisma
datasource db {
  provider  = "postgresql"
  url       = env("DATABASE_URL")   // pooled at runtime
  directUrl = env("DIRECT_URL")     // unpooled, for `prisma migrate`
}
```

The short-term Vercel deploy and the long-term VPS deploy can point at the **same
Neon database** — so moving the app off Vercel later changes only the host, never
the data. That's the whole point of keeping it host-agnostic.

---

## 2. Capacity-safe booking (the important bit)

Naive code — **WRONG**, has a check-then-act race:

```ts
// ❌ Two requests both read count = 19, both insert, class is oversold.
const count = await prisma.booking.count({ where: { classId } });
if (count < klass.capacity) {
  await prisma.booking.create({ data: { classId, userId } });
}
```

Correct: do the check and the write in **one serializable transaction** and lock
the class row, so concurrent bookings are forced to serialize.

```ts
import { Prisma, PrismaClient } from "@prisma/client";

export async function bookSeat(prisma: PrismaClient, classId: string, userId: string) {
  return prisma.$transaction(
    async (tx) => {
      // Lock the class row for the duration of the tx. Any concurrent booking for
      // the same class waits here until we commit/rollback.
      const [klass] = await tx.$queryRaw<{ id: string; capacity: number }[]>`
        SELECT id, capacity FROM "Class" WHERE id = ${classId} FOR UPDATE
      `;
      if (!klass) throw new BookingError("class_not_found");

      const taken = await tx.booking.count({ where: { classId } });
      if (taken >= klass.capacity) throw new BookingError("class_full");

      // Unique(classId, userId) in the schema also prevents double-booking.
      return tx.booking.create({ data: { classId, userId } });
    },
    { isolation: Prisma.TransactionIsolationLevel.Serializable }
  );
}

export class BookingError extends Error {}
```

Schema guardrails that back this up:

```prisma
model Class {
  id        String    @id @default(cuid())
  capacity  Int
  bookings  Booking[]
}

model Booking {
  id        String   @id @default(cuid())
  classId   String
  userId    String
  createdAt DateTime @default(now())
  class     Class    @relation(fields: [classId], references: [id])

  @@unique([classId, userId])   // a user can't book the same class twice
  @@index([classId])
}
```

Notes:
- **`FOR UPDATE` + Serializable** is belt-and-suspenders; either alone mostly works,
  but together they make oversell impossible and the unique index stops
  double-booking even under retries.
- Serializable can throw a serialization failure under contention — wrap the call in
  a small **retry (2–3 attempts)**. Keep that retry `async` and clock-injected,
  consistent with the house rule of no `time.sleep` in logic.
- This requires real interactive transactions — the reason D1 and edge libSQL
  replicas are rejected in the research.

---

## 3. Migrations & backups

```bash
# Migrations (run against directUrl)
npx prisma migrate deploy

# VPS nightly backup to Oracle Object Storage (200 GB free) — cron
pg_dump -U "$POSTGRES_USER" maavar | gzip > /backups/maavar_$(date +%F).sql.gz
pg_dump -U "$POSTGRES_USER" maayan | gzip > /backups/maayan_$(date +%F).sql.gz
# then `oci os object put ...` (or rclone) to the bucket
```

On Neon you get point-in-time restore on paid tiers and branch-based dev DBs for
free — one more reason to graduate VPS-Postgres → Neon when ops time gets scarce.
