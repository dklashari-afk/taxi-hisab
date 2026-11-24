const C="v3";
self.addEventListener("install",e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(["/static/style.css","/static/app.js"])));self.skipWaiting()});
self.addEventListener("activate",e=>e.waitUntil(clients.claim()));
self.addEventListener("fetch",e=>{const r=e.request;if(r.method!=="GET")return;
 e.respondWith(fetch(r).then(x=>{if(x.ok&&!x.redirected){const y=x.clone();caches.open(C).then(c=>c.put(r,y))}return x})
 .catch(()=>caches.match(r).then(m=>m||caches.match("/driver"))))});
