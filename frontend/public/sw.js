self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("push", (e) => {
  const { title, body } = e.data ? e.data.json() : { title: "FareSniper", body: "" };
  e.waitUntil(self.registration.showNotification(title, { body }));
});
self.addEventListener("fetch", () => {});
