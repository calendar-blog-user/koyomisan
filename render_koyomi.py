"""
テンプレートエンジン: 計算エンジン(koyomi_engine.py) + コンテンツDB(kou_content_72.jsonl)
を結合して、指定フォーマットの暦情報を生成する。LLMは一切使用しない。
"""
import json
import os
from datetime import date
from koyomi_engine import get_sekki_and_kou, moon_age, compute_kyuureki

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

KANSUJI_TSUKI = ["睦月","如月","弥生","卯月","皐月","水無月","文月","葉月","長月","神無月","霜月","師走"]
WEEKDAY_JP = ["月","火","水","木","金","土","日"]


def load_content_db(path=None):
    path = path or os.path.join(SCRIPT_DIR, "kou_content_72.jsonl")
    db = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            key = (rec["sekki"], rec["kou_label"], rec["kou_name"])
            db[key] = rec
    return db


def load_memorial_db(path=None):
    """月日をキーに記念日リストを返す。365日中、裏付けの取れた日のみ収録(72日分)。"""
    path = path or os.path.join(SCRIPT_DIR, "memorial_days.jsonl")
    db = {}
    if not os.path.exists(path):
        return db
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            db[(rec["month"], rec["day"])] = rec["entries"]
    return db


def load_sekki_description_db(path=None):
    """二十四節気そのものの意味・気候解説を返す(節気名 -> 説明文)"""
    path = path or os.path.join(SCRIPT_DIR, "sekki_description.jsonl")
    db = {}
    if not os.path.exists(path):
        return db
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            db[rec["sekki"]] = rec["description"]
    return db


def render(target_date: date, db, memorial_db=None, sekki_desc_db=None) -> str:
    sk = get_sekki_and_kou(target_date)
    ma = moon_age(target_date)
    ky = compute_kyuureki(target_date)
    key = (sk["sekki_name"], sk["kou_label"], sk["kou_name"])
    c = db.get(key)
    if c is None:
        raise KeyError(f"コンテンツDBに該当データがありません: {key}")

    weekday = WEEKDAY_JP[target_date.weekday()]
    leap = "閏" if ky["is_leap_month"] else ""

    out = []
    out.append("📅 今日の暦情報")
    out.append(f"西暦：{target_date.year}年{target_date.month}月{target_date.day}日（{weekday}）")
    out.append(f"旧暦：{leap}{ky['kyureki_month']}月{ky['kyureki_day']}日")
    out.append(f"月齢：{ma}")
    out.append("")
    out.append("☀️ 季節の移ろい")
    out.append(f"二十四節気：{sk['sekki_name']}（{sk['sekki_yomi']}）")
    if sekki_desc_db:
        out.append(sekki_desc_db.get(sk["sekki_name"], ""))
    out.append(f"七十二候：{c['kou_name']}（{c['kou_yomi']}）　― {c['kou_label']}")
    out.append(c["season_flow"])
    out.append("")
    out.append("自然の変化としては：")
    for p in c["nature_points"]:
        out.append(f"・{p}")
    out.append("")
    out.append("🚜 農事歴（農業暦）")
    out.append(f"この時期は「{c['agri_catchphrase']}」。")
    for b in c["agri_bullets"]:
        out.append(f"・{b}")
    out.append(c["agri_note"])
    out.append("")
    out.append("🏡 日本の風習・しきたり")
    out.append(c["customs_intro"])
    for b in c["customs_bullets"]:
        out.append(f"・{b}")
    out.append("")
    out.append("🎌 日本の記念日と祝日")
    memorials = (memorial_db or {}).get((target_date.month, target_date.day))
    if memorials:
        out.append("本日にちなむ記念日：")
        for m in memorials:
            out.append(f"■ {m['name']}")
            out.append(m["origin"])
    else:
        out.append("（この日に該当する記念日は未収録です）")
    out.append("")
    out.append("📚 日本の神話・伝説")
    out.append(c["mythology"])
    out.append("")
    out.append("💡 暦にまつわる文化雑学")
    out.append(c["trivia"])
    out.append("")
    out.append("🍁 自然と気象情報")
    for p in c["nature_points"]:
        out.append(f"・{p}")
    out.append("")
    out.append("🍴 旬の食材・行事食")
    out.append("旬を迎える食材：")
    for v in c["food_veg"]:
        out.append(f"・{v}")
    for v in c["food_fruit"]:
        out.append(f"・{v}")
    for v in c["food_seafood"]:
        out.append(f"・{v}")
    out.append(c["food_note"])
    out.append("")
    out.append("行事食としては")
    for v in c["event_food"]:
        out.append(f"・{v}")
    out.append("などが親しまれます。")
    out.append("")
    out.append("🌸 季節の草木と花言葉")
    out.append(f"季節の花：{c['flower_name']}（{c['flower_yomi']}）")
    out.append(f"・花言葉：「{c['flower_meaning']}」")
    out.append(f"・{c['flower_note']}")
    out.append("")
    out.append("その他の植物：")
    for p in c["other_plants"]:
        out.append(f"・{p['name']}（{p['note']}）")
    out.append("")
    out.append("🌕 月や星の暦・天文情報")
    out.append(c["astronomy_moon"])
    out.append("")
    out.append("星空では：")
    for s in c["astronomy_stars"]:
        out.append(f"・{s}")
    out.append("")
    out.append("🎨 伝統工芸・民芸品")
    out.append("この季節に関連して作られるものとしては：")
    for cr in c["craft"]:
        out.append(f"・{cr['name']}：{cr['note']}")
    out.append("")
    out.append("📖 祭事の背景・神話伝説")
    out.append(c["festival_background"])
    out.append("")
    out.append("🎼 伝統芸能")
    out.append(c["performing_art"])
    return "\n".join(out)


def get_full_data(target_date: date, db, memorial_db=None, sekki_desc_db=None) -> dict:
    """サイト表示・today.json用に、全セクションぶんの構造化データを返す"""
    sk = get_sekki_and_kou(target_date)
    ma = moon_age(target_date)
    ky = compute_kyuureki(target_date)
    key = (sk["sekki_name"], sk["kou_label"], sk["kou_name"])
    c = db.get(key)
    if c is None:
        raise KeyError(f"コンテンツDBに該当データがありません: {key}")

    weekday = WEEKDAY_JP[target_date.weekday()]
    leap = "閏" if ky["is_leap_month"] else ""
    memorials = (memorial_db or {}).get((target_date.month, target_date.day)) or []
    sekki_description = (sekki_desc_db or {}).get(sk["sekki_name"], "")

    return {
        "date": target_date.isoformat(),
        "weekday": weekday,
        "kyureki": f"{leap}{ky['kyureki_month']}月{ky['kyureki_day']}日",
        "moon_age": ma,
        "sekki_name": sk["sekki_name"],
        "sekki_yomi": sk["sekki_yomi"],
        "sekki_description": sekki_description,
        "kou_name": c["kou_name"],
        "kou_yomi": c["kou_yomi"],
        "kou_label": c["kou_label"],
        "season_flow": c["season_flow"],
        "nature_points": c["nature_points"],
        "agri_catchphrase": c["agri_catchphrase"],
        "agri_bullets": c["agri_bullets"],
        "agri_note": c["agri_note"],
        "customs_intro": c["customs_intro"],
        "customs_bullets": c["customs_bullets"],
        "memorials": memorials,
        "mythology": c["mythology"],
        "trivia": c["trivia"],
        "food_veg": c["food_veg"],
        "food_fruit": c["food_fruit"],
        "food_seafood": c["food_seafood"],
        "food_note": c["food_note"],
        "event_food": c["event_food"],
        "flower_name": c["flower_name"],
        "flower_yomi": c["flower_yomi"],
        "flower_meaning": c["flower_meaning"],
        "flower_note": c["flower_note"],
        "other_plants": c["other_plants"],
        "astronomy_moon": c["astronomy_moon"],
        "astronomy_stars": c["astronomy_stars"],
        "craft": c["craft"],
        "festival_background": c["festival_background"],
        "performing_art": c["performing_art"],
    }


if __name__ == "__main__":
    db = load_content_db()
    mdb = load_memorial_db()
    sdb = load_sekki_description_db()
    result = render(date(2026, 9, 18), db, mdb, sdb)
    print(result)
