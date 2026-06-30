// Cardcom recurring-membership webhook handler (Next.js 14 App Router).
// Place at: app/api/webhooks/cardcom/route.ts
//
// Cardcom posts here on payment events for recurring (תשלום חוזר) charges:
// successful renewal, failed renewal, cancellation. We verify authenticity,
// then update membership state idempotently.
//
// Setup: in the Cardcom dashboard, set the recurring "indicator/callback" URL to
//   https://maavar.<domain>/api/webhooks/cardcom?secret=<CARDCOM_WEBHOOK_SECRET>
// Cardcom's classic API doesn't HMAC-sign callbacks, so we gate on a shared
// secret in the query string (kept out of logs) AND re-verify the transaction
// server-side against Cardcom before trusting it.

import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export const runtime = "nodejs"; // needs full Node (DB + outbound fetch), not edge

export async function POST(req: NextRequest) {
  // 1) Authenticate the caller via shared secret (constant-time compare).
  const provided = req.nextUrl.searchParams.get("secret") ?? "";
  const expected = process.env.CARDCOM_WEBHOOK_SECRET ?? "";
  if (!safeEqual(provided, expected)) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }

  // 2) Cardcom posts form-encoded fields. Parse defensively.
  const form = await req.formData();
  const dealId = String(form.get("InternalDealNumber") ?? form.get("DealNumber") ?? "");
  const recurringId = String(form.get("AccountId") ?? form.get("RecurringId") ?? "");
  // We set ReturnValue=membership.id at checkout (see lib/cardcom.ts), so this is
  // the reliable correlation key even before a stable recurringId exists.
  const membershipId = String(form.get("ReturnValue") ?? "");
  const responseCode = String(form.get("ResponseCode") ?? "");
  const operation = String(form.get("Operation") ?? ""); // charge | cancel | fail

  if (!dealId && !recurringId && !membershipId) {
    return NextResponse.json({ ok: false, error: "missing_ids" }, { status: 400 });
  }

  // 3) Trust-but-verify: re-confirm the transaction with Cardcom server-side.
  //    (A spoofed POST that knew the secret still can't fake a real deal.)
  const verified = await verifyWithCardcom(dealId);
  if (!verified) {
    return NextResponse.json({ ok: false, error: "unverified" }, { status: 402 });
  }

  // 4) Idempotent state update keyed on the unique deal id, so Cardcom retries
  //    don't double-apply. Wrap membership extension + payment log in one tx.
  await prisma.$transaction(async (tx) => {
    const already = await tx.paymentEvent.findUnique({ where: { dealId } });
    if (already) return; // seen this deal already — no-op

    await tx.paymentEvent.create({
      data: { dealId, recurringId, operation, responseCode },
    });

    const success = responseCode === "0";
    // Correlate on membershipId (ReturnValue) first; fall back to recurringId for
    // renewal events where ReturnValue isn't echoed back.
    const membership = membershipId
      ? await tx.membership.findUnique({ where: { id: membershipId } })
      : await tx.membership.findFirst({ where: { recurringId } });
    if (!membership) return;

    if (success && operation !== "cancel") {
      await tx.membership.update({
        where: { id: membership.id },
        data: {
          status: "active",
          // On first charge, persist the real recurring handle for future renewals.
          recurringId: recurringId || membership.recurringId,
          // extend one billing period from the later of now / current expiry
          currentPeriodEnd: addMonth(maxDate(new Date(), membership.currentPeriodEnd)),
        },
      });
    } else if (operation === "cancel") {
      await tx.membership.update({
        where: { id: membership.id },
        data: { status: "canceled" },
      });
    } else {
      // failed renewal — mark past_due; a separate dunning job emails via Resend.
      await tx.membership.update({
        where: { id: membership.id },
        data: { status: "past_due" },
      });
    }
  });

  // Cardcom expects a 200 to stop retrying.
  return NextResponse.json({ ok: true });
}

// --- helpers ---

async function verifyWithCardcom(dealId: string): Promise<boolean> {
  if (!dealId) return false;
  // Cardcom "GetTransactionInfo"-style lookup. Endpoint/fields per your Cardcom
  // account's API version; this is the shape, not a guaranteed URL.
  const res = await fetch("https://secure.cardcom.solutions/Interface/BillGoldGetLowProfileIndicator.aspx", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      terminalnumber: process.env.CARDCOM_TERMINAL ?? "",
      username: process.env.CARDCOM_API_NAME ?? "",
      // some endpoints want password; keep it server-side only
      InternalDealNumber: dealId,
    }),
  });
  if (!res.ok) return false;
  const text = await res.text();
  // Cardcom returns ResponseCode=0 on a real, successful deal.
  return /(^|&)ResponseCode=0(&|$)/.test(text);
}

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function addMonth(d: Date): Date {
  const n = new Date(d);
  n.setMonth(n.getMonth() + 1);
  return n;
}
function maxDate(a: Date, b: Date | null): Date {
  return !b || a > b ? a : b;
}
