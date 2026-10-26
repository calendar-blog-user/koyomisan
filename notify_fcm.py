"""
毎日実行するスクリプト(不特定多数の利用者向け)。2段階に分けて実行できる:

  python notify_fcm.py build : サイトのデータを作る(Firebase不要)
      public/today.json と、public/data/YYYY-MM-DD.json(前日〜14日先)を生成する。
      画面はブラウザの日付(日本時間)に合うファイルを読むので、朝の自動実行が遅れたり失敗したりしても、
      数日のあいだは正しい日付の暦が表示される。
  python notify_fcm.py send  : 通知のきっかけがある日だけ、購読者全員にFirebase Cloud Messagingで通知する。
      購読者が選んだ都市の日の出・日の入り・月の出・月の入りを添える。都市ごとに本文を作り分ける。
      通知のきっかけ: 二十四節気・七十二候の切り替わり／国民の祝日／重要な祭日／主要な年中行事／記念日
                      ／雑節／選日(天赦日・寅の日・巳の日・己巳の日・不成就日)／一粒万倍日／新月・満月
      (雑節・選日・一粒万倍日・新月・満月は、calendar_data.py の設定で、種類ごとに通知のきっかけにするかどうかを切り替えられる。
       六曜と、新月・満月以外の天文トピックスは、サイトには表示するが通知のきっかけにはしない)。
      通知のタイトルは「今日は〇〇（区分）」の形で、何の日だから通知しているかが分かるようにする。
  python notify_fcm.py send --test : テスト通知。通知のきっかけの有無にかかわらず、購読者全員に「テスト通知」を送る
      (通知の登録ができているか、スマホに届くかを確かめるため。GitHub Actionsの手動実行で選べる)
  python notify_fcm.py       : 両方を続けて実行する(従来どおり)

GitHub Actionsでは「build → サイトのデプロイ → send」の順に実行する。通知の送信に失敗しても、
サイトの更新は先に済んでいるようにするため。

必要な環境変数(sendのみ):
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

ROOT = os.path.dirname(os.path.abspath(__file__))

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


WINDOW_PAST_DAYS = 1      # 前日から(日付をまたぐ直前の閲覧に備える)
WINDOW_FUTURE_DAYS = 14   # 14日先まで(朝の自動実行が止まっても、数日は正しい日付が出る)


def _dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_site_data(today: date, dbs: dict) -> dict:
    """public/data/YYYY-MM-DD.json(前日〜14日先)と public/today.json を作り、今日のデータを返す。"""
    generated_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    today_data = None
    for offset in range(-WINDOW_PAST_DAYS, WINDOW_FUTURE_DAYS + 1):
        d = today + timedelta(days=offset)
        data = get_full_data(d, dbs)
        data["generated_at"] = generated_at   # いつ作ったデータか(サイトの下部に表示。古いままの原因調べに使う)
        _dump(os.path.join(PUBLIC_DIR, "data", f"{d.isoformat()}.json"), data)
        if offset == 0:
            today_data = data
            _dump(os.path.join(PUBLIC_DIR, "today.json"), data)   # 旧版のサイトや、日付別ファイルが無いときの予備
    print(f"サイトのデータを作成しました: {today - timedelta(days=WINDOW_PAST_DAYS)} 〜 {today + timedelta(days=WINDOW_FUTURE_DAYS)}"
          f"(今日={today}、生成={generated_at})")
    return today_data


def build_test_message(data: dict, city_id: str):
    """(タイトル, 本文): 通知が届くことを確かめるためのテスト通知。選んだ都市の時刻も添える。"""
    city = CITY_BY_ID[city_id]
    t = data["sun_moon"][city_id]
    f = lambda v: v if v else "なし"
    body = (f"通知の登録はできています。\n今日は{data['gregorian_label']}、{data['sekki_name']}・{data['kou_name']}（{data['kou_label']}）です。\n"
            f"【{city['name']}】日の出 {f(t['sunrise'])}／日の入り {f(t['sunset'])}／月の出 {f(t['moonrise'])}／月の入り {f(t['moonset'])}")
    return "こよみさんのテスト通知", body


def resolve_site_url() -> str:
    """通知をタップしたときに開くURL。環境変数 SITE_URL を使う。
    未設定(GitHubの変数が空)や、httpsで始まらない値のままFCMに渡すと、送信が拒否されてしまうため、
    firebase.json のサイト名(例: koyomi → https://koyomi.web.app)で代用する。"""
    url = (os.environ.get("SITE_URL") or "").strip()
    if url.startswith("https://"):
        return url
    fallback = None
    try:
        with open(os.path.join(ROOT, "firebase.json"), encoding="utf-8") as f:
            site = json.load(f)["hosting"].get("site")
        fallback = f"https://{site}.web.app" if site else None
    except (OSError, ValueError, KeyError):
        pass
    print(f"【注意】SITE_URL が未設定か、https で始まっていません(値: {url!r})。"
          + (f"firebase.json のサイト名から {fallback} を使います。GitHubの Variables の SITE_URL を設定してください。"
             if fallback else "通知のリンクなしで送ります。GitHubの Variables の SITE_URL を設定してください。"), file=sys.stderr)
    return fallback or ""


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
    """(送信成功数, 無効になった端末のトークンのリスト)。失敗した端末は、理由をログに出す。"""
    invalid, sent = [], 0
    for batch_tokens in chunked(tokens, 500):  # FCMの一括送信は最大500件/回
        webpush = messaging.WebpushConfig(
            # Urgency=high: スマホがスリープ(Doze)中でも、すぐ届けるように依頼する
            #   (指定しないと通常の優先度になり、スマホが動き出すまで配信が待たされることがある)
            # TTL=43200(12時間): 電波が届かなかった端末には、12時間以内に届ける。それ以降は破棄
            #   (「今日は〇〇」という通知が、翌日以降に届いてしまうのを防ぐ)
            headers={"Urgency": "high", "TTL": "43200"},
            notification=messaging.WebpushNotification(icon="icon-192.png"),
            fcm_options=messaging.WebpushFCMOptions(link=click_url) if click_url else None,
        )
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            webpush=webpush,
            tokens=batch_tokens,
        )
        response = messaging.send_each_for_multicast(message)
        sent += response.success_count
        for idx, resp in enumerate(response.responses):
            if resp.success:
                continue
            exc = resp.exception
            print(f"    送信失敗(端末…{batch_tokens[idx][-6:]}): {type(exc).__name__}: {exc}", file=sys.stderr)
            # 端末側で通知が解除された・トークンが失効した場合だけ、登録情報を削除する。
            # (INVALID_ARGUMENT などは、通知の中身や設定の不備でも起こるため、削除しない)
            if isinstance(exc, messaging.UnregisteredError):
                invalid.append(batch_tokens[idx])
    return sent, invalid


def send_all(groups: dict, full_data: dict, click_url: str, test: bool = False) -> int:
    """都市ごとに通知を送る。ある都市の送信に失敗しても、ほかの都市は送る。失敗した都市の数を返す。"""
    total = sum(len(v) for v in groups.values())
    if total == 0:
        print("購読者がまだいません。通知は送信されませんでした。")
        return 0
    print("購読者: 合計" + str(total) + "件（" + "、".join(f"{CITY_BY_ID[c]['name']} {len(t)}件" for c, t in groups.items()) + "）")
    sent_total, invalid_all, failed = 0, [], 0
    for city_id, tokens in groups.items():
        title, body = build_test_message(full_data, city_id) if test else build_message(full_data, city_id)
        try:
            sent, invalid = send_to_city(tokens, title, body, click_url)
        except Exception as e:   # noqa: BLE001 (原因をログに残して、次の都市へ進む)
            failed += 1
            print(f"  {CITY_BY_ID[city_id]['name']}: 送信に失敗しました: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        sent_total += sent
        invalid_all += invalid
        print(f"  {CITY_BY_ID[city_id]['name']}: {sent}/{len(tokens)}件 「{title}」")
    print(f"{sent_total} / {total} 件に通知を送信しました。")
    try:
        remove_invalid_tokens(invalid_all)
    except Exception as e:   # noqa: BLE001
        print(f"無効なトークンの削除に失敗しました(通知の送信には影響しません): {e}", file=sys.stderr)
    return failed


def send_notifications(today: date, full_data: dict, test: bool = False) -> int:
    if test:
        print("テスト通知を送ります(通知のきっかけの有無にかかわらず、購読者全員に送信)")
        init_firebase()
        return send_all(get_subscribers_by_city(), full_data, resolve_site_url(), test=True)
    reasons = full_data["reasons"]   # 今日が何の日か(通知のきっかけ)
    if not reasons:
        print(f"{today} は「{full_data['sekki_name']}・{full_data['kou_name']}（{full_data['kou_label']}）」の期間中で、"
              "通知のきっかけ(七十二候の切り替わり・祝日・祭日・主要な年中行事・記念日・雑節・選日・一粒万倍日・新月・満月)がないため、通知は送信しません。")
        return 0
    print("通知のきっかけ: " + "、".join(r["short"] for r in reasons))
    init_firebase()
    return send_all(get_subscribers_by_city(), full_data, resolve_site_url())


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:]) or ["all"]
    test = "--test" in args
    mode = [a for a in args if not a.startswith("--")][0] if [a for a in args if not a.startswith("--")] else "all"
    if mode not in ("build", "send", "all"):
        print("使い方: python notify_fcm.py [build|send [--test]]", file=sys.stderr)
        sys.exit(2)
    if test and mode != "send":
        print("--test は send と一緒に指定してください", file=sys.stderr)
        sys.exit(2)

    today = today_jst()
    dbs = load_databases()
    full_data = build_site_data(today, dbs) if mode in ("build", "all") else get_full_data(today, dbs)
    if mode == "build":
        return

    failed = send_notifications(today, full_data, test=test)
    if failed:
        sys.exit(1)   # 失敗した都市があれば、Actionsの実行を失敗にして気づけるようにする(サイトの更新は済んでいる)


if __name__ == "__main__":
    main()
