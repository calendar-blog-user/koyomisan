// バックグラウンド(アプリを開いていない/画面がスリープ中)でも通知を受け取るためのService Worker
importScripts("https://www.gstatic.com/firebasejs/10.13.2/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.13.2/firebase-messaging-compat.js");
importScripts("firebase-config.js");

firebase.initializeApp(firebaseConfig);

// 通知の表示そのものはFCM(Firebase)が自動で行う。
// サーバー(notify_fcm.py)がnotification付きで送っているため、ここで showNotification を
// 重ねて呼ぶと同じ通知が2つ表示されてしまう。そのため onBackgroundMessage は設定しない。
// (通知のタイトル・本文・アイコン・タップ時の遷移先は、すべて送信側で指定している)
firebase.messaging();

// ホーム画面に追加(インストール)できるようにするための最小限のキャッシュ処理。
// 「ネットワーク優先」にして、オンラインの時は常に最新のページ・今日のデータを表示する。
// (キャッシュ優先にすると、古いindex.htmlが固定されてしまうため)
const CACHE_NAME = "koyomi-cache-v2";
const CORE_ASSETS = ["/", "/index.html", "/manifest.json", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.allSettled(CORE_ASSETS.map((asset) => cache.add(asset)))
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok && new URL(event.request.url).origin === self.location.origin) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
