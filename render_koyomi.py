"""
テンプレートエンジン:
  計算エンジン(koyomi_engine.py / sunmoon.py / calendar_extras.py) + コンテンツDB(kou_content_72.jsonl 等)
を結合して、その日の暦情報を作る。LLMは一切使用しない。

  get_full_data() : サイト(today.json)・通知用の構造化データ(唯一のデータの取りまとめ口)
  render_text()   : 指定フォーマット(絵文字見出し)のテキスト。確認用。get_full_data()の出力から作る。
"""
import json
import os
from datetime import date, timedelta

import astro_events as ae
import calendar_data as cd
import calendar_extras as ce
import kyusei as kyu
from koyomi_engine import get_sekki_and_kou, moon_age, compute_kyuureki, moon_phase_name
from sunmoon import CITIES, CITY_BY_ID, DEFAULT_CITY_ID, sun_moon_times, moon_tonight_text, day_length_fields

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


# ------------------------------------------------------------------
# データ読み込み
# ------------------------------------------------------------------
def _read_jsonl(name):
    path = os.path.join(SCRIPT_DIR, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_content_db():
    """七十二候ごとのコンテンツ: (節気名, 初候/次候/末候, 候名) -> レコード"""
    return {(r["sekki"], r["kou_label"], r["kou_name"]): r for r in _read_jsonl("kou_content_72.jsonl")}


def load_sekki_description_db():
    """二十四節気そのものの意味・気候解説: 節気名 -> 説明文"""
    return {r["sekki"]: r["description"] for r in _read_jsonl("sekki_description.jsonl")}


def load_kyureki_month_db():
    """旧暦月名(和風月名)とその解説: 月番号 -> {name, yomi, description}"""
    return {r["month"]: r for r in _read_jsonl("kyureki_month_names.jsonl")}


def load_databases():
    return {"kou": load_content_db(), "sekki": load_sekki_description_db(), "kyureki_month": load_kyureki_month_db()}


# ------------------------------------------------------------------
# 「今日は何の日か」(通知のきっかけ)。通知のタイトル・本文と、サイトの今日の暦カードで共通に使う
# ------------------------------------------------------------------
MAX_REASON_LINES = 5   # 通知の本文に並べる「きっかけ」の最大数


def is_new_kou_day(target_date: date) -> bool:
    """今日が七十二候の切り替わり初日かどうか(前日と候が違えばTrue)。
    二十四節気の切り替わり日は、その節気の初候の初日なので、これに含まれる。"""
    key = lambda k: (k["sekki_name"], k["kou_label"], k["kou_name"])
    return key(get_sekki_and_kou(target_date)) != key(get_sekki_and_kou(target_date - timedelta(days=1)))


def first_sentence(text: str, limit: int = 60, min_len: int = 25) -> str:
    """説明文の冒頭(通知用の短縮版)。最初の一文が短いときは、次の一文まで含める(全体はlimit字まで)。"""
    sentences = [x + "。" for x in text.split("。") if x]
    if not sentences:
        return text
    out = sentences[0]
    for nxt in sentences[1:]:
        if len(out) >= min_len or len(out) + len(nxt) > limit:
            break
        out += nxt
    return out if len(out) <= limit else out[: limit - 1] + "…"


def build_reasons(data: dict) -> list:
    """通知のきっかけ(=今日が何の日か)を、重要な順に並べて返す。
    順番: 国民の祝日 → 二十四節気 → 重要な祭日 → 主要な年中行事 → 雑節 → 天赦日 → 記念日
          → 七十二候(次候・末候) → 新月・満月 → 選日(寅の日・巳の日・己巳の日・不成就日) → 一粒万倍日
      short : 「文化の日」（国民の祝日）のような短い言い方(タイトル・サイトの見出し用)
      line  : 通知の本文に1行ずつ並べる説明
    雑節・選日・一粒万倍日は、calendar_data.py の NOTIFY_ZASSETSU / NOTIFY_SENJITSU /
    NOTIFY_ICHIRYU_MANBAI で、種類ごとに通知のきっかけにするかどうかを切り替えられる。
    新月・満月は、calendar_data.py の NOTIFY_MOON_PHASE で、種類ごとに切り替えられる。
    六曜と、新月・満月以外の天文トピックスは、通知のきっかけにしない。"""
    items = data["notify_items"]

    def item_reason(it):
        label = it["category"]
        if label == "国民の祝日" and it.get("kind", "祝日") != "祝日":
            label = "休日"       # 振替休日・国民の休日
        return {"kind": "item", "label": label, "name": it["name"],
                "short": f"「{it['name']}」（{label}）",
                "line": f"■{label}「{it['name']}」：{first_sentence(it['desc'])}"}

    holidays = [item_reason(i) for i in items if i["category"] == "国民の祝日"]
    saijitsu = [item_reason(i) for i in items if i["category"] == "重要な祭日"]
    events = [item_reason(i) for i in items if i["category"] == "年中行事"]
    kinenbi = [item_reason(i) for i in items if i["category"] == "記念日"]

    # 雑節・選日・一粒万倍日(calendar_data.py の設定でONにした種類だけ)
    zassetsu = [item_reason(i) for i in data["zassetsu"]] if cd.NOTIFY_ZASSETSU else []
    senjitsu = [i for i in data["senjitsu"] if cd.NOTIFY_SENJITSU.get(i["name"], False)]
    tenshanichi = [item_reason(i) for i in senjitsu if i["name"] == "天赦日"]
    senjitsu_other = [item_reason(i) for i in senjitsu if i["name"] != "天赦日"]
    ichiryu = ([item_reason({**data["ichiryu_manbai"], "category": "選日"})]   # 一粒万倍日も、選日の一つとして表示する
               if data["ichiryu_manbai"] and cd.NOTIFY_ICHIRYU_MANBAI else [])

    sekki, kou = [], []
    if data["kou_changed"]:
        if data["kou_label"] == "初候":
            sekki.append({"kind": "sekki", "label": "二十四節気", "name": data["sekki_name"],
                          "short": f"二十四節気「{data['sekki_name']}」の始まり",
                          "line": f"■二十四節気「{data['sekki_name']}」の始まり：{first_sentence(data['sekki_description'])}"
                                  f"七十二候は「{data['kou_name']}」（初候）に入りました。"})
        else:
            kou.append({"kind": "kou", "label": "七十二候", "name": data["kou_name"],
                        "short": f"七十二候「{data['kou_name']}」（{data['kou_label']}）の始まり",
                        "line": f"■七十二候「{data['kou_name']}」（{data['kou_label']}）の始まり：{first_sentence(data['season_flow'], 70)}"})
    # 新月・満月(日本時間で、その日のうちに朔・望の瞬間がある日)
    moon_desc = {
        "朔": "月が太陽と同じ方向にあり、夜空に月は見えません。旧暦では、新月の日が月の1日です。",
        "望": "月が太陽の反対側にあり、まるく光ります。日の入りのころに東の空から昇り、夜通し空にあります。",
    }
    moon = []
    for p in data.get("moon_phases", []):
        if p["kind"] in moon_desc and cd.NOTIFY_MOON_PHASE.get(p["kind"], False):
            name = p["label"].split("（")[0]   # 「新月」「満月」
            moon.append({"kind": "moon", "label": "月の満ち欠け", "name": name,
                         "short": f"「{name}」（月の満ち欠け）",
                         "line": f"■月の満ち欠け「{name}」：{p['time']}に{p['label']}となります。{moon_desc[p['kind']]}"})
    return holidays + sekki + saijitsu + events + zassetsu + tenshanichi + kinenbi + kou + moon + senjitsu_other + ichiryu


def build_message(data: dict, city_id: str):
    """(タイトル, 本文) を作る。タイトルで「今日は何の日だから通知しているか」を伝え、
    本文には、きっかけを区分つきで1行ずつ並べ、最後にその都市の日の出入り・月の出入りを添える。"""
    reasons = data["reasons"]
    if not reasons:
        raise ValueError("通知のきっかけがない日です")
    title = "今日は" + reasons[0]["short"] + (f" ほか{len(reasons) - 1}件" if len(reasons) > 1 else "")

    lines = [r["line"] for r in reasons[:MAX_REASON_LINES]]
    if len(reasons) > MAX_REASON_LINES:
        lines.append(f"ほか{len(reasons) - MAX_REASON_LINES}件")
    city = CITY_BY_ID[city_id]
    t = data["sun_moon"][city_id]
    f = lambda v: v if v else "なし"
    lines.append(f"【{city['name']}】日の出 {f(t['sunrise'])}／日の入り {f(t['sunset'])}／"
                 f"月の出 {f(t['moonrise'])}／月の入り {f(t['moonset'])}")
    return title, "\n".join(lines)


# ------------------------------------------------------------------
# 構造化データ
# ------------------------------------------------------------------
def get_full_data(target_date: date, dbs: dict) -> dict:
    sk = get_sekki_and_kou(target_date)
    ma = moon_age(target_date)
    ky = compute_kyuureki(target_date)
    key = (sk["sekki_name"], sk["kou_label"], sk["kou_name"])
    c = dbs["kou"].get(key)
    if c is None:
        raise KeyError(f"コンテンツDBに該当データがありません: {key}")

    weekday = WEEKDAY_JP[target_date.weekday()]
    leap = "閏" if ky["is_leap_month"] else ""
    month_info = dbs["kyureki_month"].get(ky["kyureki_month"], {})
    cal = ce.day_calendar_info(target_date, ky)

    # 日の出入り・月の出入り・南中: 地点(政令指定都市＋東京)ごと
    sun_moon = {}
    for city in CITIES:
        t = sun_moon_times(target_date, city["lat"], city["lon"])
        t["moon_tonight"] = moon_tonight_text(target_date, city["lat"], city["lon"], t)
        t.update(day_length_fields(target_date, city["lat"], city["lon"]))   # 昼の長さ・前日との差
        sun_moon[city["id"]] = t

    data = {
        "date": target_date.isoformat(),
        "weekday": weekday,
        "gregorian_label": f"{target_date.year}年{target_date.month}月{target_date.day}日（{weekday}）",
        "kanshi": cal["kanshi"],
        "kanshi_info": ce.kanshi_info(target_date),   # 干支の読み・説明(サイトの「日の干支」の欄用)
        "wareki": ce.wareki_info(target_date),        # 和暦
        "kyusei": kyu.kyusei_info(target_date),       # 九星気学(日・月・年)
        "tide": ce.tide_info(ky["kyureki_day"]),      # 潮回り(大潮・中潮など)
        "kyureki": f"{leap}{ky['kyureki_month']}月{ky['kyureki_day']}日",
        "kyureki_month_num": ky["kyureki_month"],
        "kyureki_month_name": month_info.get("name", ""),
        "kyureki_month_yomi": month_info.get("yomi", ""),
        "kyureki_month_description": month_info.get("description", ""),
        "is_leap_month": ky["is_leap_month"],
        "rokuyo": {**ce.rokuyo_info(ky["kyureki_month"], ky["kyureki_day"]), "note": cd.ROKUYO_NOTE},
        "moon_age": ma,
        "moon_age_label": f"{ma:.1f}",   # 国立天文台の表記(正午月齢・小数第1位)に合わせる
        "moon_phase_name": moon_phase_name(ky["kyureki_day"]),
        "cities": [{"id": x["id"], "name": x["name"], "pref": x["pref"]} for x in CITIES],
        "default_city": DEFAULT_CITY_ID,
        "sun_moon": sun_moon,
        "sekki_name": sk["sekki_name"],
        "sekki_yomi": sk["sekki_yomi"],
        "sekki_description": dbs["sekki"].get(sk["sekki_name"], ""),
        "kou_name": c["kou_name"],
        "kou_yomi": c["kou_yomi"],
        "kou_label": c["kou_label"],
        "season_flow": c["season_flow"],
        "nature_points": c["nature_points"],
        "climate_note": c.get("climate_note", ""),
        "weather_points": c.get("weather_points", c["nature_points"]),
        "agri_catchphrase": c["agri_catchphrase"],
        "agri_bullets": c["agri_bullets"],
        "agri_note": c["agri_note"],
        "customs_intro": c["customs_intro"],
        "customs_bullets": c["customs_bullets"],
        # 🎌 国民の祝日 / 重要な祭日 / 年中行事 / 記念日
        "holidays": cal["holidays"],
        "saijitsu": cal["saijitsu"],
        "events": cal["events"],
        "kinenbi": cal["kinenbi"],
        # 🔖 雑節・選日
        "zassetsu": cal["zassetsu"],
        "ichiryu_manbai": cal["ichiryu_manbai"],
        "senjitsu": cal["senjitsu"],
        # 🌕 天文トピックス(月の満ち欠け・日食月食・流星群)
        "astro": ae.astro_summary(target_date),
        "moon_phases": ae.phases_on(target_date),   # その日に朔・上弦・望・下弦の瞬間があれば、その種類と時刻(通知のきっかけの判定に使う)
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
        # 通知のきっかけになる項目(国民の祝日 → 重要な祭日 → 主要な年中行事 → 記念日の順)
        "notify_items": ce.notification_items(cal),
        "kou_changed": is_new_kou_day(target_date),
    }
    # 今日が何の日か(通知のきっかけ)。通知のタイトル・本文と、サイトの今日の暦カードで使う
    data["reasons"] = build_reasons(data)
    return data


# ------------------------------------------------------------------
# テキスト表示(確認用)
# ------------------------------------------------------------------
def _fmt(v):
    return v if v else "なし"


def render_text(data: dict, city_id: str = DEFAULT_CITY_ID) -> str:
    city = CITY_BY_ID[city_id]
    sm = data["sun_moon"][city_id]
    o = []
    o.append("📅 今日の暦情報")
    o.append(f"西暦：{data['gregorian_label']}")
    o.append(f"旧暦：{data['kyureki']}（{data['moon_phase_name']}）")
    k = data["kanshi_info"]
    o.append(f"日の干支：{k['name']}（{k['yomi']}）")
    o.append(f"　{k['desc']}")
    kd = data["kyusei"]
    o.append(f"九星：{kd['day']['name']}（{kd['day']['yomi']}）　年：{kd['year']['name']}／月：{kd['month']['name']}")
    o.append(f"　{kd['day']['desc']}")
    o.append(f"和暦：{data['wareki']['label']}")
    o.append(f"潮回り：{data['tide']['name']}（{data['tide']['yomi']}）　{data['tide']['desc']}")
    r = data["rokuyo"]
    o.append(f"六曜：{r['name']}（{r['yomi']}）― {r['timing']}")
    o.append(f"　{r['desc']}")
    o.append(f"正午月齢：{data['moon_age_label']}")
    o.append(f"【{city['name']}】日の出 {_fmt(sm['sunrise'])}／日南中 {_fmt(sm['solar_noon'])}／日の入り {_fmt(sm['sunset'])}")
    o.append(f"　月の出 {_fmt(sm['moonrise'])}／月南中 {_fmt(sm['moon_transit'])}／月の入り {_fmt(sm['moonset'])}")
    if sm.get("day_length"):
        o.append(f"　昼の長さ {sm['day_length']}（{sm['day_diff']}）")
    if data["kyureki_month_name"]:
        o.append(f"旧暦{data['kyureki_month_num']}月は「{data['kyureki_month_name']}（{data['kyureki_month_yomi']}）」。{data['kyureki_month_description']}")
    o += ["", data["climate_note"], "", "☀️ 季節の移ろい",
          f"二十四節気：{data['sekki_name']}（{data['sekki_yomi']}）", data["sekki_description"],
          f"七十二候：{data['kou_name']}（{data['kou_yomi']}）　― {data['kou_label']}", data["season_flow"], "",
          "自然の変化としては："] + [f"・{p}" for p in data["nature_points"]]
    o += ["", "🚜 農事歴（農業暦）", f"この時期は「{data['agri_catchphrase']}」。"] + [f"・{b}" for b in data["agri_bullets"]] + [data["agri_note"]]
    o += ["", "🏡 日本の風習・しきたり", data["customs_intro"]] + [f"・{b}" for b in data["customs_bullets"]]

    o += ["", "🎌 日本の記念日と祝日"]
    any_item = False
    for title, items in (("国民の祝日", data["holidays"]), ("重要な祭日", data["saijitsu"]),
                         ("年中行事", data["events"]), ("記念日", data["kinenbi"])):
        for it in items:
            any_item = True
            o += [f"■ {it['name']}（{title}）", it["desc"]]
    if not any_item:
        o.append("（この日に該当する祝日・行事・記念日はありません）")

    o += ["", "🔖 雑節・選日"]
    zs = list(data["zassetsu"]) + ([data["ichiryu_manbai"]] if data["ichiryu_manbai"] else []) + list(data["senjitsu"])
    if zs:
        for it in zs:
            o += [f"■ {it['name']}", it["desc"]]
    else:
        o.append("（この日に該当する雑節・選日はありません）")

    o += ["", "📚 日本の神話・伝説", data["mythology"], "", "💡 暦にまつわる文化雑学", data["trivia"],
          "", "🍁 自然と気象情報"] + [f"・{p}" for p in data["weather_points"]]
    o += ["", "🍴 旬の食材・行事食", "旬を迎える食材："] + [f"・{v}" for v in data["food_veg"] + data["food_fruit"] + data["food_seafood"]]
    o += [data["food_note"], "", "行事食としては"] + [f"・{v}" for v in data["event_food"]] + ["などが親しまれます。"]
    o += ["", "🌸 季節の草木と花言葉", f"季節の花：{data['flower_name']}（{data['flower_yomi']}）",
          f"・花言葉：「{data['flower_meaning']}」", f"・{data['flower_note']}", "", "その他の植物："]
    o += [f"・{p['name']}（{p['note']}）" for p in data["other_plants"]]
    o += ["", "🌕 月や星の暦・天文情報", sm["moon_tonight"], data["astronomy_moon"]]
    for it in data["astro"]["items"]:
        o.append(f"【{it['title']}】")
        o += [f"・{ln}" for ln in it["lines"]]
    o += ["", "星空では："] + [f"・{s}" for s in data["astronomy_stars"]]
    o += ["", "🎨 伝統工芸・民芸品", "この季節に関連して作られるものとしては："] + [f"・{c['name']}：{c['note']}" for c in data["craft"]]
    o += ["", "📖 祭事の背景・神話伝説", data["festival_background"], "", "🎼 伝統芸能", data["performing_art"]]
    return "\n".join(o)


if __name__ == "__main__":
    dbs = load_databases()
    d = get_full_data(date(2026, 10, 9), dbs)
    print(render_text(d, "okayama"))
