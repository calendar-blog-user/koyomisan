"""
public/firebase-config.js の値に、書き間違い(読み間違い・コピーミス)がないかを確認する。

    python check_config.py

特に VAPID キー(通知用の鍵)は、長い英数字で、l/I/1 や O/0 を取り違えやすい。
VAPIDキーは楕円曲線(P-256)の公開鍵なので、1文字でも違うと「曲線上の点」として成立しない。
この性質を使って、正しいキーかどうかを確実に判定できる。
GitHub Actionsでも毎回最初に実行し、誤りがあればその時点で失敗させて、原因をログに出す。
"""
import base64
import os
import re
import sys

from cryptography.hazmat.primitives.asymmetric import ec

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "firebase-config.js")


def vapid_problem(key: str):
    """VAPIDキーに問題があればその説明を、問題なければ None を返す"""
    try:
        raw = base64.urlsafe_b64decode(key + "=" * (-len(key) % 4))
    except Exception:  # noqa: BLE001
        return "使えない文字が含まれています(英数字と - _ だけのはずです)"
    if len(raw) != 65 or raw[0] != 4:
        return f"長さが正しくありません(87文字のはずですが、{len(key)}文字です)"
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
    except ValueError:
        return ("鍵として成立しません。1文字以上が間違っています(特に l と I と 1、O と 0 の取り違えに注意)。"
                "Firebaseコンソールの「コピー」ボタンで、値を直接コピーして貼り付けてください")
    return None


def read_value(text: str, name: str):
    m = re.search(rf'{name}\s*[:=]\s*"([^"]*)"', text)
    return m.group(1) if m else None


def main() -> int:
    text = open(CONFIG_PATH, encoding="utf-8").read()
    problems = []
    vals = {k: read_value(text, k) for k in ("apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId", "VAPID_KEY")}
    for k, v in vals.items():
        if not v:
            problems.append(f"{k} が設定されていません")
    if not problems:
        if not vals["apiKey"].startswith("AIza") or len(vals["apiKey"]) != 39:
            problems.append("apiKey の形式が正しくありません(AIza で始まる39文字のはずです)")
        if not vals["messagingSenderId"].isdigit():
            problems.append("messagingSenderId は数字だけのはずです")
        if not re.fullmatch(rf'1:{vals["messagingSenderId"]}:web:[0-9a-f]+', vals["appId"]):
            problems.append("appId の形式が正しくないか、messagingSenderId と一致しません")
        if not vals["authDomain"].startswith(vals["projectId"] + "."):
            problems.append("authDomain が projectId と一致しません")
        v = vapid_problem(vals["VAPID_KEY"])
        if v:
            problems.append("VAPID_KEY: " + v)
    if problems:
        print("firebase-config.js に問題があります:")
        for p in problems:
            print("  ・" + p)
        return 1
    print("firebase-config.js: OK (VAPIDキーは、P-256の公開鍵として成立します)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
