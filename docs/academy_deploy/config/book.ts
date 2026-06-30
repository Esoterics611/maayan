// Booking server action. Place at: app/actions/book.ts
//
// Wraps the capacity-safe transaction (PRISMA_DB.md) as a Next.js server action:
// authenticated, race-proof (FOR UPDATE + Serializable), with a retry loop for
// serialization failures and a waitlist fallback when the class is full.
// Returns a typed result with a Hebrew message for the UI.

"use server";

import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { requireUser } from "@/auth";
import { revalidatePath } from "next/cache";

type BookResult =
  | { ok: true; status: "booked" | "waitlisted"; messageHe: string }
  | { ok: false; code: "class_not_found" | "already_booked" | "error"; messageHe: string };

const MAX_RETRIES = 3;

export async function bookClass(classId: string): Promise<BookResult> {
  const user = await requireUser();

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const status = await prisma.$transaction(
        async (tx) => {
          // Lock the class row; concurrent bookings for this class serialize here.
          const rows = await tx.$queryRaw<{ id: string; capacity: number }[]>`
            SELECT id, capacity FROM "Class" WHERE id = ${classId} FOR UPDATE
          `;
          const klass = rows[0];
          if (!klass) throw new NotFound();

          const existing = await tx.booking.findUnique({
            where: { classId_userId: { classId, userId: user.id } },
          });
          if (existing) throw new AlreadyBooked();

          const taken = await tx.booking.count({
            where: { classId, status: "booked" },
          });
          const status = taken < klass.capacity ? "booked" : "waitlisted";

          await tx.booking.create({
            data: { classId, userId: user.id, status },
          });
          return status as "booked" | "waitlisted";
        },
        { isolation: Prisma.TransactionIsolationLevel.Serializable }
      );

      revalidatePath(`/classes/${classId}`);
      return status === "booked"
        ? { ok: true, status, messageHe: "נרשמת בהצלחה לשיעור." }
        : { ok: true, status, messageHe: "השיעור מלא — נוספת לרשימת ההמתנה." };
    } catch (e) {
      if (e instanceof NotFound) {
        return { ok: false, code: "class_not_found", messageHe: "השיעור לא נמצא." };
      }
      if (e instanceof AlreadyBooked) {
        return { ok: false, code: "already_booked", messageHe: "כבר נרשמת לשיעור הזה." };
      }
      // Postgres serialization failure (40001) — retry a couple of times.
      if (isSerializationFailure(e) && attempt < MAX_RETRIES) continue;
      console.error("bookClass failed", e);
      return { ok: false, code: "error", messageHe: "אירעה שגיאה. נסה שוב." };
    }
  }
  return { ok: false, code: "error", messageHe: "השרת עמוס כרגע. נסה שוב." };
}

class NotFound extends Error {}
class AlreadyBooked extends Error {}

function isSerializationFailure(e: unknown): boolean {
  return (
    e instanceof Prisma.PrismaClientKnownRequestError &&
    // P2034 = write conflict / deadlock / serialization failure surfaced by Prisma
    (e.code === "P2034" || (typeof e.meta?.code === "string" && e.meta.code === "40001"))
  );
}
