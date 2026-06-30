// Cardcom outbound checkout — the half that *starts* a recurring membership.
// Place at: lib/cardcom.ts
//
// Flow:
//   1. startMembershipCheckout(user, plan) creates a Membership row in `trialing`
//      and asks Cardcom for a hosted "Low Profile" payment page set to recurring.
//   2. We redirect the user to the returned URL; they enter card + installments.
//   3. On success Cardcom posts to /api/webhooks/cardcom (cardcom-webhook.ts),
//      which flips the membership to `active` and extends currentPeriodEnd.
//
// The recurringId returned here is the join key the webhook matches on, so we
// store it on the Membership immediately.
//
// NOTE: exact endpoint/field names track your Cardcom account's API version.
// This is the typed shape + control flow; confirm fields against your terminal's
// API docs before going live. Money is in agorot (ILS minor units) throughout.

import { prisma } from "@/lib/db";
import type { Plan, User } from "@prisma/client";

const CARDCOM_BASE = "https://secure.cardcom.solutions/Interface";

interface CardcomConfig {
  terminal: string;
  apiName: string;
  apiPassword: string;
  rootUrl: string; // e.g. https://maavar.example.co.il
}

function config(): CardcomConfig {
  const { CARDCOM_TERMINAL, CARDCOM_API_NAME, CARDCOM_API_PASSWORD, AUTH_URL } = process.env;
  if (!CARDCOM_TERMINAL || !CARDCOM_API_NAME || !CARDCOM_API_PASSWORD || !AUTH_URL) {
    throw new Error("cardcom_config_missing");
  }
  return {
    terminal: CARDCOM_TERMINAL,
    apiName: CARDCOM_API_NAME,
    apiPassword: CARDCOM_API_PASSWORD,
    rootUrl: AUTH_URL,
  };
}

export interface CheckoutResult {
  membershipId: string;
  redirectUrl: string; // send the user here
}

/**
 * Begin a recurring membership purchase. Creates the trialing Membership and a
 * hosted recurring payment page. Returns the URL to redirect the buyer to.
 */
export async function startMembershipCheckout(user: User, plan: Plan): Promise<CheckoutResult> {
  const cfg = config();

  // Create the membership up front in `trialing`; the webhook activates it.
  const membership = await prisma.membership.create({
    data: { userId: user.id, planId: plan.id, status: "trialing" },
  });

  // Cardcom wants the major-unit amount; convert agorot -> shekel with 2 decimals.
  const amountIls = (plan.priceAgorot / 100).toFixed(2);

  const params = new URLSearchParams({
    TerminalNumber: cfg.terminal,
    UserName: cfg.apiName,
    APILevel: "10",
    Operation: "ChargeAndCreateToken", // token enables future recurring charges
    Language: "he",
    CoinID: "1", // 1 = ILS
    SumToBill: amountIls,
    ProductName: plan.name,
    // Round-trip identifiers so the webhook can correlate the membership.
    ReturnValue: membership.id,
    // Where Cardcom sends the browser + the server-to-server indicator.
    SuccessRedirectUrl: `${cfg.rootUrl}/checkout/success?m=${membership.id}`,
    ErrorRedirectUrl: `${cfg.rootUrl}/checkout/error?m=${membership.id}`,
    IndicatorUrl: `${cfg.rootUrl}/api/webhooks/cardcom?secret=${process.env.CARDCOM_WEBHOOK_SECRET ?? ""}`,
    // Israeli installments — let the buyer split (tashlumim).
    MaxNumOfPayments: "12",
    MinNumOfPayments: "1",
  });

  const res = await fetch(`${CARDCOM_BASE}/LowProfile.aspx`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params,
  });
  if (!res.ok) {
    await markFailed(membership.id);
    throw new Error(`cardcom_http_${res.status}`);
  }

  // Classic LowProfile returns url-encoded body: ResponseCode, url, LowProfileCode...
  const parsed = new URLSearchParams(await res.text());
  if (parsed.get("ResponseCode") !== "0") {
    await markFailed(membership.id);
    throw new Error(`cardcom_error_${parsed.get("ResponseCode")}`);
  }

  const redirectUrl = parsed.get("url");
  const lowProfileCode = parsed.get("LowProfileCode");
  if (!redirectUrl) {
    await markFailed(membership.id);
    throw new Error("cardcom_no_url");
  }

  // LowProfileCode is the pending recurring handle until the webhook supplies the
  // final AccountId/recurringId; store it so we can reconcile if the webhook is late.
  if (lowProfileCode) {
    await prisma.membership.update({
      where: { id: membership.id },
      data: { recurringId: lowProfileCode },
    });
  }

  return { membershipId: membership.id, redirectUrl };
}

async function markFailed(membershipId: string): Promise<void> {
  await prisma.membership.update({
    where: { id: membershipId },
    data: { status: "canceled" },
  });
}
