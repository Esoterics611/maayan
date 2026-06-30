# Academy hosting & infra research (Maavar + Maayan)

> Research dated **2026-06-30**. This concerns the **Next.js membership academy**
> (Maavar = teaching tech English; Maayan academy = separate educational site),
> *not* the Python `maayan` RAG that owns this repo. It lives here as the
> long-term infrastructure track. The short-term Vercel deploy is a separate,
> disposable path — see [§ Short-term Vercel](#short-term-vercel-track) — and is
> intentionally compatible with this plan.

Stack under consideration:
- Next.js 14 App Router (TypeScript strict, server actions)
- Prisma ORM (SQLite dev → Postgres prod)
- Auth.js (credentials + role-based)
- Resend (transactional email)
- Capacity-limited class booking (transactional DB writes)

---

## ⚠️ Three 2026 changes that shape the answer

1. **Oracle cut the Always Free ARM tier in half.** As of June 2026 it is
   **2 OCPU / 12 GB**, not 4/24. Existing instances aren't all enforced yet, but
   new ones are capped and a free instance gets **stopped** until resized down.
   Plan around 2/12. ([TerminalBytes](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026/),
   [Linuxiac](https://linuxiac.com/oracle-quietly-cuts-free-tier-ampere-a1-resources-in-half/))
2. **Vercel Hobby forbids commercial use.** A paid membership site is explicitly a
   violation (revenue-generating projects). Commercial use ⇒ Pro at $20/mo. So
   Vercel is *not* a free option long-term — fine as the short-term track only.
   ([Vercel pricing](https://vercel.com/pricing), [breakdown](https://schematichq.com/blog/vercel-pricing))
3. **Lemon Squeezy is winding down** post-Stripe acquisition (confirmed Jan 2026,
   migrating merchants to Stripe Managed Payments, slower support). Don't build new
   on it. ([Dodo](https://dodopayments.com/blogs/lemonsqueezy-alternatives))

---

## 1. Hosting

| Option | Cost after free | Sleep? | Fit |
|---|---|---|---|
| **Oracle Always Free (ARM)** | $0 (now 2 OCPU/12 GB) | No | ✅ Handles ~200 concurrent SSR users on 2/12. You own all ops. |
| **Vercel Pro** | $20/user/mo + overages | No | ✅ Native Next.js, zero-ops. Serverless ⇒ no file SQLite (use Neon/Turso). Commercial ⇒ Pro. |
| **Railway** | ~$5/mo Hobby + usage | No | ✅ Easiest managed path. Postgres add-on pricey at large specs, tiny for this load. |
| **Render** | $7/mo web + $6/mo PG | Free tier sleeps 15 min | ✅ Predictable flat pricing. Avoid free web tier (cold starts hurt booking). |
| **Fly.io** | ~$2–5 compute, ~$34 real PG | No | ✅ Cheapest at scale, more hands-on. |
| **Cloudflare Pages+Workers+D1** | $0–5 | No | ❌ Reject — D1 has no interactive transactions; booking needs row locking. |

**Oracle viability for ~200 concurrent:** Yes. Next.js SSR is not CPU-heavy per
request; 2 ARM cores + 12 GB behind **Caddy** (auto-HTTPS) runs Next + Postgres
for that load. Real cost is *your time*: patching, backups, monitoring.

---

## 2. Database

**Decision driver: capacity-limited booking is a transactional-integrity
problem.** Booking the last seat needs `SELECT ... FOR UPDATE` / serializable
isolation so two parents can't both grab seat #20. That rules options in/out:

| DB | Free tier | Verdict |
|---|---|---|
| **Neon** (serverless PG) | 100 CU-hrs/mo, 0.5 GB, 5 GB egress, no card | ✅ **Recommended.** Real PG + transactions, Prisma-native. → $19/mo Launch. Use **pooled** connection string on serverless hosts. ([pricing](https://neon.com/pricing)) |
| **Supabase** | 500 MB, 50k MAU, **pauses after 1 wk idle** | ✅ Good if you want bundled auth/storage. Auto-pause = booking failures at low traffic. ([pricing](https://supabase.com/pricing)) |
| **Turso** (libSQL) | 5 GB, 500M row reads | ⚠️ Edge replicas eventually consistent; thinner Prisma support. Don't put booking writes here. ([pricing](https://turso.tech/pricing)) |
| **Cloudflare D1** | SQLite at edge | ❌ No interactive transactions + replica lag. |
| **Oracle 23ai free DB** | On Always Free (2 ADBs) | ⚠️ Prisma support poor. If on Oracle, run self-hosted Postgres in Docker instead. |

**On "SQLite dev → Postgres prod":** keep it, but run **Postgres in prod from day
one** and **Postgres locally too** (Docker) so dev/prod match. File SQLite cannot
work on serverless and makes the booking transaction story fragile. Prisma makes
the switch one `provider` + `DATABASE_URL` change.

---

## 3. Payments (Israel-based operator, Israeli parents)

**Israeli consumers expect tashlumim (interest-free installments) and a Hebrew tax
invoice (חשבונית מס).** Stripe and merchant-of-record platforms handle neither
well → use a **local Israeli processor**.

| Processor | Recurring? | Why |
|---|---|---|
| **Cardcom** ⭐ | ✅ Native recurring API + webhooks | Modern REST API, recurring endpoints, Israeli tax invoices, installments. Best fit for a Next.js membership site. |
| **Meshulam / Grow** | ✅ | Popular with Israeli SMBs; supports **Bit**, installments, invoicing. |
| **Tranzila** | ✅ | Cheapest, no-monthly-fee tier; older API. |
| **Stripe** | ✅ | Now in Israel + ILS, but weaker local-card/installment/Hebrew-invoice support; messy clearing-license history. Reserve for future *international/English* audience. ([Stripe Israel](https://stripe.com/resources/more/payments-in-israel)) |
| **Paddle / Lemon (MoR)** | ✅ 5%+50¢ (+0.5% subs) | Handles global VAT, but only for *global digital* sales; no Israeli installments/invoices. Lemon winding down. |

**Recommendation:** **Cardcom** for recurring memberships. Use Meshulam/Grow if
Bit matters. Reserve Stripe/Paddle for a future international Maavar audience.
Comparison source: [Israeli gateways](https://danielmashkov.com/insights/israeli-payment-gateways-comparison).

---

## 4. Marketing tools (low/no cost)

- **Email — split by job:** keep **Resend transactional** (auth, booking confirms;
  3k/mo free). Add **Brevo for marketing** (300/day ≈ 9k/mo free, list mgmt). Never
  blast marketing through Resend — it wrecks transactional deliverability.
  ([Brevo free tier](https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan))
- **Analytics:** **Umami self-hosted** ($0, same VPS) or **Plausible** ($9/mo /
  free self-host). Privacy-friendly, no cookie banner.
- **WhatsApp:** start with **wa.me deep links** (free). Graduate to WhatsApp
  Business API (360dialog/Twilio) only when you need templated broadcasts.
- **CRM:** Airtable/Notion free tier is plenty early. Don't self-build.
- **Hebrew SEO:** `lang="he" dir="rtl"`, `hreflang="he-IL"`, schema.org `Course` +
  `Organization`, Hebrew Open Graph. Keep **nikkud out of URLs/slugs/meta**.
  Israeli search is ~all Google → fast SSR + RTL-correct structured data wins.

---

## 5. Recommended stack

**Architecture:** one **Turborepo monorepo**, Maavar + Maayan as separate Next.js
apps sharing packages (`auth`, `db`, `ui`, `email`). **Combine infrastructure,
separate apps + DB schemas** — one host, one Postgres instance with two schemas
(or two DBs), one Resend/Brevo account, shared Auth.js config. Clean isolation so a
Maavar bug can't touch Maayan data.

**Concrete stack:**
- **Host:** Oracle Always Free VPS (2 OCPU/12 GB) + **Caddy** + Docker Compose.
  *Zero-ops alternative: Railway ~$5–10/mo.*
- **DB:** Postgres — self-hosted in Docker on the VPS (free) or Neon free
  (safer backups, recommended). Prisma + pooled connection.
- **Auth:** Auth.js credentials + RBAC.
- **Email:** Resend (transactional) + Brevo (marketing).
- **Payments:** Cardcom (recurring, ILS, installments, invoices).
- **Analytics:** Umami self-hosted.

**Estimated monthly cost:**

| Stage | Hosting + DB | Payments | Email/mktg | Total infra |
|---|---|---|---|---|
| 0–50 students | Oracle Free + self-host PG = $0 | Cardcom fees (~1.5–3% + small monthly) | Resend+Brevo free = $0 | **~$0 + fees** |
| 50–200 | Oracle Free, or Railway $10 + Neon free/$19 | Cardcom fees | Brevo $9 if list grows | **~$0–40** |
| 200+ | Railway/Render $7–15 + Neon Launch $19 (or Supabase Pro $25) | Cardcom fees | Brevo $9–18 | **~$35–60** |

**Migration path Oracle Free → paid** (lift-and-shift, no rewrite because it's all
Docker + Caddy + Prisma):
1. Start: Oracle Free VPS, Postgres in Docker, nightly `pg_dump` to Oracle Object
   Storage (200 GB free).
2. Outgrow box / tired of ops: point app at **Neon** (restore dump), keep VPS or
   move app to **Railway/Render** — same Docker image, set `DATABASE_URL`.
3. Scale: Neon Launch + Render Starter; Cloudflare free CDN in front. DNS cutover.

**Combine Maavar + Maayan?** Yes — share infra (one VPS, one PG instance, one
email/auth surface) but keep separate apps + DB schemas. Saves cost, single ops
surface, clean data isolation.

---

## Short-term Vercel track

The short-term deploy goes to **Vercel** and is intentionally compatible with the
long-term plan above:
- Use **Vercel Pro** (Hobby forbids commercial use) **or** keep it pre-revenue/
  staging on Hobby until launch.
- Vercel is serverless ⇒ **no file SQLite**. Point Prisma at **Neon** (pooled
  connection string) — the *same* Neon DB the long-term plan uses, so there's
  **nothing to migrate** when you move the app off Vercel later; only the host
  changes. Keep `DATABASE_URL` the single switch.
- Everything else (Auth.js, Resend, Cardcom) is host-agnostic and carries over
  unchanged.

This is the same discipline as the Python `maayan` RAG's `GENERATION_BACKEND`
swap: construction at the edges, config-driven, so the host is swappable.

---

## Sources

- [Oracle free tier cut 2026](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026/) ·
  [Linuxiac](https://linuxiac.com/oracle-quietly-cuts-free-tier-ampere-a1-resources-in-half/)
- [Vercel pricing](https://vercel.com/pricing) · [breakdown](https://schematichq.com/blog/vercel-pricing)
- [Neon pricing](https://neon.com/pricing) · [Supabase pricing](https://supabase.com/pricing) · [Turso pricing](https://turso.tech/pricing)
- [Railway/Render/Fly](https://thesoftwarescout.com/railway-vs-render-2026-best-platform-for-deploying-apps/)
- [Israeli payment gateways](https://danielmashkov.com/insights/israeli-payment-gateways-comparison) · [Stripe Israel](https://stripe.com/resources/more/payments-in-israel)
- [Stripe vs Paddle vs Lemon](https://www.globalsolo.global/blog/stripe-vs-paddle-vs-lemon-squeezy-2026) · [Lemon winding down](https://dodopayments.com/blogs/lemonsqueezy-alternatives)
- [Brevo free tier](https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan)
