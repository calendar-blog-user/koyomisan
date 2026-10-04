"""
毎日実行するスクリプト(不特定多数の利用者向け):
  1. 今日の日付で暦情報を生成(計算エンジン + コンテンツDB、LLM不使用)
  2. public/today.json を更新(サイトのプレビューカード表示用、毎日更新)
  3. 七十二候が「切り替わった初日」だけ、Firestoreに登録されている購読者(FCMトークン)全員に
     Firebase Cloud Messaging経由でプッシュ通知を送信する(約5日に1回、年間72回)

必要な環境変数:
  FIREBASE_SERVICE_ACCOUNT_JSON : Firebaseサービスアカウントの秘密鍵(JSON文字列そのもの)
  SITE_URL                      : 通知をタップしたときに開くURL(例: https://your-project.web.app)
"""
import json
import os
import sys
from datetime import date, timedelta

import firebase_admin
from firebase_admin import credentials, firestore, messaging

from render_koyomi import get_sekki_and_kou, load_content_db, load_memorial_db, load_sekki_description_db, get_full_data

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")


def is_new_kou_day(target_date) -> bool:
    """今日が七十二候の切り替わり初日かどうかを判定する(前日と候が違えばTrue)"""
    today_kou = get_sekki_and_kou(target_date)
    yesterday_kou = get_sekki_and_kou(target_date - timedelta(days=1))
    today_key = (today_kou["sekki_name"], today_kou["kou_label"], today_kou["kou_name"])
    yesterday_key = (yesterday_kou["sekki_name"], yesterday_kou["kou_label"], yesterday_kou["kou_name"])
    return today_key != yesterday_key


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


def get_all_tokens():
    db = firestore.client()
    tokens = []
    for doc in db.collection("subscribers").stream():
        d = doc.to_dict()
        t = d.get("token") or doc.id
        if t:
            tokens.append(t)
    return tokens


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


def send_to_all(tokens, title, body, click_url):
    if not tokens:
        print("購読者がまだいません。通知は送信されませんでした。")
        return

    invalid = []
    sent = 0
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

    print(f"{sent} / {len(tokens)} 件に通知を送信しました。")
    remove_invalid_tokens(invalid)


def main():
    init_firebase()
    site_url = os.environ.get("SITE_URL", "/")

    today = date.today()
    db = load_content_db()
    mdb = load_memorial_db()
    sdb = load_sekki_description_db()
    full_data = get_full_data(today, db, mdb, sdb)
    memorials = full_data["memorials"]

    # サイト表示用のtoday.jsonは毎日更新する(通知の有無に関わらず、いつ開いても今日の内容が見える)
    write_today_json(full_data)

    should_notify = is_new_kou_day(today) or bool(memorials)
    if not should_notify:
        print(f"{today} は「{full_data['sekki_name']}・{full_data['kou_name']}（{full_data['kou_label']}）」の期間中で、"
              "候の切り替わり日でも記念日のある日でもないため、通知は送信しません(サイトの表示のみ更新)。")
        return

    if memorials:
        title = f"「{memorials[0]['name']}」　― {full_data['sekki_name']}・{full_data['kou_name']}（{full_data['kou_label']}）"
    else:
        title = f"{full_data['kou_name']}（{full_data['kou_label']}）　― {full_data['sekki_name']}"
    body = full_data["season_flow"]
    if memorials:
        body = f"「{memorials[0]['name']}」の日。{body}"

    tokens = get_all_tokens()
    send_to_all(tokens, title, body, site_url)


if __name__ == "__main__":
    main()
