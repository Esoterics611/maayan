// Database seed. Place at: prisma/seed.ts
// Wire into package.json:  "prisma": { "seed": "tsx prisma/seed.ts" }
// Run:  npx prisma db seed
//
// Creates one ADMIN, a sample course+class (capacity 20), and a monthly plan.
// Idempotent via upsert — safe to re-run.

import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const adminEmail = process.env.SEED_ADMIN_EMAIL ?? "admin@example.co.il";
  const adminPassword = process.env.SEED_ADMIN_PASSWORD ?? "change-me-now-8chars";

  const admin = await prisma.user.upsert({
    where: { email: adminEmail },
    update: {},
    create: {
      email: adminEmail,
      name: "Academy Admin",
      role: "ADMIN",
      locale: "he",
      passwordHash: await bcrypt.hash(adminPassword, 12),
    },
  });

  const plan = await prisma.plan.upsert({
    where: { slug: "monthly" },
    update: {},
    create: {
      slug: "monthly",
      name: "מנוי חודשי", // monthly membership
      priceAgorot: 9900, // ₪99.00
      intervalDays: 30,
    },
  });

  const course = await prisma.course.upsert({
    where: { slug: "tech-english-foundations" },
    update: {},
    create: {
      slug: "tech-english-foundations",
      title: "אנגלית טכנולוגית — יסודות",
      titleEn: "Tech English — Foundations",
      description: "קורס מבוא לאנגלית טכנולוגית.",
      classes: {
        create: {
          title: "שיעור פתיחה",
          titleEn: "Opening session",
          capacity: 20,
          startsAt: new Date(Date.now() + 7 * 24 * 3600 * 1000),
          endsAt: new Date(Date.now() + 7 * 24 * 3600 * 1000 + 3600 * 1000),
          instructorId: admin.id,
        },
      },
    },
  });

  console.log({ admin: admin.email, plan: plan.slug, course: course.slug });
}

main()
  .then(() => prisma.$disconnect())
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
