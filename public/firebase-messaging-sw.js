// バックグラウンド(アプリを開いていない/画面がスリープ中)でも通知を受け取るためのService Worker
importScripts("https://www.gstatic.com/firebasejs/10.13.2/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.13.2/firebase-messaging-compat.js");
importScripts("firebase-config.js");

firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// バックグラウンド受信時の通知の見た目を指定する
messaging.onBackgroundMessage((payload) => {
  const title = payload.notification?.title || "こよみ";
  const options = {
    body: payload.notification?.body || "",
    icon: "icon-192.png",
    badge: "icon-192.png",
  };
  self.registration.showNotification(title, options);
});

// PWAをホーム画面から開けるようにするための最低限のキャッシュ処理
const CACHE_NAME = "koyomi-cache-v1";
const CORE_ASSETS = ["/", "/index.html", "/manifest.json", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
