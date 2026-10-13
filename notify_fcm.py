"""
毎日実行するスクリプト(不特定多数の利用者向け):
  1. 今日(日本時間)の暦情報を、全地点(政令指定都市＋東京)ぶん生成し、public/today.json を更新する(毎日)
  2. 次の「通知のきっかけ」がある日だけ、購読者全員にFirebase Cloud Messaging経由で通知を送る。
     通知には、購読者が選んだ都市の日の出・日の入り・月の出・月の入りを添える。
       ・二十四節気・七十二候の切り替わり日
       ・国民の祝日(振替休日・国民の休日を含む)
       ・重要な祭日
       ・主要な年中行事
       ・記念日
     (雑節・選日・六曜・天文トピックスは、サイトには表示するが通知のきっかけにはしない)
     通知のタイトルは「今日は〇〇（区分）」の形で、何の日だから通知しているかが分かるようにする。

必要な環境変数:
  FIREBASE_SERVICE_ACCOUNT_JSON : Firebaseサービスアカウントの秘密鍵(JSON文字列そのもの)
  SITE_URL                      : 通知をタップしたときに開くURL(例: https://your-project.web.app)
"""
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import firebase_admin
from firebase_admin import credentials, firestore, messaging

from render_koyomi import get_full_data, load_databases, build_message, is_new_kou_day  # is_new_kou_dayは互換のため再公開
from sunmoon import CITY_BY_ID, DEFAULT_CITY_ID

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

JST = timezone(timedelta(hours=9))

def today_jst() -> date:
    """日本時間の今日の日付を返す。
    GitHub Actionsの実行環境はUTCで動いており、date.today()だと朝7時(JST)の実行時に
    前日の日付になってしまうため、必ずJSTを明示して取得する。"""
    return datetime.now(JST).date()


def init_firebase():
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        print("環境変数 FIREBASE_SERVICE_ACCOUNT_JSON が設定されていません。", file=sys.stderr)
        sys.exit(1)
    cred = credentials.Certificate(json.loads(sa_json))
    firebase_admin.initialize_app(cred)


def write_today_json(full_data):
    path = os.path.join(PUBLIC_DIR, "today.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)
    print(f"today.json を更新しました(全セクション収録): {path}")


def get_subscribers_by_city() -> dict:
    """Firestoreの購読者を、都市ごとにまとめる。都市が未設定・不明な購読者は既定の都市(東京)として扱う。"""
    db = firestore.client()
    groups = defaultdict(list)
    for doc in db.collection("subscribers").stream():
        d = doc.to_dict() or {}
        token = d.get("token") or doc.id
        city = d.get("city")
        if token:
            groups[city if city in CITY_BY_ID else DEFAULT_CITY_ID].append(token)
    return groups


def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def remove_invalid_tokens(invalid_tokens):
    if not invalid_tokens:
        return
    db = firestore.client()
    batch = db.batch()
    for t in invalid_tokens:
        batch.delete(db.collection("subscribers").document(t))
    batch.commit()
    print(f"無効になっていたトークンを{len(invalid_tokens)}件削除しました。")


def send_to_city(tokens, title, body, click_url) -> tuple:
    """(送信成功数, 無効トークンのリスト)"""
    invalid, sent = [], 0
    for batch_tokens in chunked(tokens, 500):  # FCMの一括送信は最大500件/回
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            webpush=messaging.WebpushConfig(
                fcm_options=messaging.WebpushFCMOptions(link=click_url),
                notification=messaging.WebpushNotification(icon="icon-192.png"),
            ),
            tokens=batch_tokens,
        )
        response = messaging.send_each_for_multicast(message)
        sent += response.success_count
        for idx, resp in enumerate(response.responses):
            if not resp.success:
                code = getattr(resp.exception, "code", "")
                if code in ("NOT_FOUND", "UNREGISTERED", "INVALID_ARGUMENT"):
                    invalid.append(batch_tokens[idx])
    return sent, invalid


def send_all(groups: dict, full_data: dict, click_url: str):
    total = sum(len(v) for v in groups.values())
    if total == 0:
        print("購読者がまだいません。通知は送信されませんでした。")
        return
    sent_total, invalid_all = 0, []
    for city_id, tokens in groups.items():
        title, body = build_message(full_data, city_id)
        sent, invalid = send_to_city(tokens, title, body, click_url)
        sent_total += sent
        invalid_all += invalid
        print(f"  {CITY_BY_ID[city_id]['name']}: {sent}/{len(tokens)}件 「{title}」")
    print(f"{sent_total} / {total} 件に通知を送信しました。")
    remove_invalid_tokens(invalid_all)


def main():
    init_firebase()
    site_url = os.environ.get("SITE_URL", "/")

    today = today_jst()
    full_data = get_full_data(today, load_databases())

    # サイト表示用のtoday.jsonは毎日更新する(通知の有無に関わらず、いつ開いても今日の内容が見える)
    write_today_json(full_data)

    reasons = full_data["reasons"]   # 今日が何の日か(通知のきっかけ)
    if not reasons:
        print(f"{today} は「{full_data['sekki_name']}・{full_data['kou_name']}（{full_data['kou_label']}）」の期間中で、"
              "通知のきっかけ(七十二候の切り替わり・祝日・祭日・主要な年中行事・記念日)がないため、"
              "通知は送信しません(サイトの表示のみ更新)。")
        return

    print("通知のきっかけ: " + "、".join(r["short"] for r in reasons))
    send_all(get_subscribers_by_city(), full_data, site_url)


if __name__ == "__main__":
    main()
