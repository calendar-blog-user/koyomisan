// Googleアナリティクス(GA4)の読み込み。
// 測定ID(G- から始まる文字列)が正しい形でないときは、何も読み込まず、何も送りません。
(function () {
  var GA_MEASUREMENT_ID = "G-WMH18H3R68";   // Googleアナリティクスの「測定ID」

  // 測定IDが未設定でも、サイト側の呼び出し(trackEvent)がエラーにならないようにしておく
  window.trackEvent = function () {};
  if (!/^G-[A-Z0-9]{6,}$/.test(GA_MEASUREMENT_ID)) return;

  var s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_MEASUREMENT_ID;
  document.head.appendChild(s);

  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  gtag("js", new Date());
  gtag("config", GA_MEASUREMENT_ID);

  // 通知の登録・解除など、ページの表示以外の出来事を記録する。通知のトークンなど、個人を特定できる情報は送らない。
  window.trackEvent = function (name, params) {
    try { gtag("event", name, params || {}); } catch (e) { /* 記録に失敗しても、サイトの動作には影響させない */ }
  };
})();
