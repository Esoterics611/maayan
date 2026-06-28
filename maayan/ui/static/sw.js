/* maayan service worker — makes the UI installable + offline-tolerant for reads.
 *
 * Rules (mirror docs/BUILD_PLAN_PHASE6.md, Prompt 23):
 *   - Only ever touch the cache for same-origin GET requests.
 *   - NEVER cache mutations (POST/PUT/PATCH/DELETE) or API reads (/ask, /annotate,
 *     /threads, /terms, /retract, /stats, /compose, /api/*, …) — those are always
 *     network. Stale grounded answers / capture state would be a correctness bug.
 *   - Cache-first only for a tiny set of static shell assets.
 *   - The app shell (navigations) is network-first, falling back to a cached shell
 *     when offline so the installed app still opens.
 */
const CACHE = "maayan-v1";
const STATIC = ["/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(STATIC)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function isStatic(url) {
  return STATIC.includes(url.pathname) || url.pathname.startsWith("/icon-");
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // The cache is only ever for same-origin GETs. Mutations + cross-origin fall through.
  if (req.method !== "GET" || url.origin !== self.location.origin) return;

  // Cache-first for the static shell assets.
  if (isStatic(url)) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(req, copy));
            }
            return res;
          }),
      ),
    );
    return;
  }

  // App-shell navigations: network-first, cache the live shell, fall back offline.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok && !res.redirected && res.type === "basic") {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put("/", copy));
          }
          return res;
        })
        .catch(() => caches.match("/").then((hit) => hit || Response.error())),
    );
    return;
  }

  // Everything else (API reads, etc.) → straight to network, never cached.
});
