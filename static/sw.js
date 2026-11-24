const C = "v6";
const PRECACHE = [
  "/static/driver.html",
  "/static/style.css",
  "/static/app.js"
];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(C).then(c => c.addAll(PRECACHE))
  );
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k))))
      .then(() => clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const r = e.request;
  if (r.method !== "GET") return;
  if (new URL(r.url).origin !== location.origin) return;

  e.respondWith(
    fetch(r).then(x => {
      if (x.ok && !x.redirected) {
        const y = x.clone();
        caches.open(C).then(c => c.put(r, y));
      }
      return x;
    }).catch(() => {
      // Navigation requests ke liye driver.html fallback
      if (r.mode === "navigate") {
        return caches.match("/static/driver.html");
      }
      return caches.match(r);
    })
  );
});