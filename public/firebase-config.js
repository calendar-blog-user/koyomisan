// ▼▼▼ ここを、あなたのFirebaseプロジェクトの値に書き換えてください ▼▼▼
const firebaseConfig = {
  apiKey: "AIzaSyD7QwVWKFagZ_JuUHzh8B2n1AAWIiW39-M",
  authDomain: "koyomi-8b720.firebaseapp.com",
  projectId: "koyomi-8b720",
  storageBucket: "koyomi-8b720.firebasestorage.app",
  messagingSenderId: "519059910067",
  appId: "1:519059910067:web:9b2cf4a9bb3977f8946fc6"
};

// Firebaseコンソール → プロジェクトの設定 → Cloud Messaging → ウェブ構成 →
// 「ウェブプッシュ証明書」で生成した鍵のペア(公開鍵)をここに貼り付けてください。
const VAPID_KEY = "BPEpYTaZuRS2vk_oTe5TBwo7xy-KyRKOSrOp9y_qX6B7L0LQYVOFWUeYWLy7oz2js8cMjLm933pGkPWUD-0Zx7s";
// ▲▲▲ ここまで ▲▲▲

if (typeof window !== "undefined") {
  window.firebaseConfig = firebaseConfig;
  window.VAPID_KEY = VAPID_KEY;
}