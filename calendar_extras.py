"""
日付から、干支・六曜・雑節・一粒万倍日・国民の祝日・年中行事・重要な祭日を求める。
二十四節気・朔(新月)の計算は koyomi_engine.py(天文計算)を使う。LLMは使わない。

国民の祝日は現行の祝日法(2022年以降)の規定で計算する。法改正があった場合は要見直し。
"""
import json
import os
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import ephem

import calendar_data as cd
from koyomi_engine import find_longitude_crossing, get_sekki_and_kou

JST = timezone(timedelta(hours=9))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


# ------------------------------------------------------------------
# 干支(日)
# ------------------------------------------------------------------
def kanshi_index(d: date) -> int:
    """その日の六十干支の番号(0=甲子 ... 59=癸亥)。2000-01-01=戊午(54)で検算済み。"""
    jdn = d.toordinal() + 1721425
    return (jdn - 11) % 60


def kanshi_name(d: date) -> str:
    i = kanshi_index(d)
    return STEMS[i % 10] + BRANCHES[i % 12]


def kanshi_info(d: date) -> dict:
    """その日の干支と、サイトに出す説明(読み・十干の五行と陰陽・十二支の動物)"""
    i = kanshi_index(d)
    stem, branch = STEMS[i % 10], BRANCHES[i % 12]
    stem_yomi, gogyo, inyo = cd.STEMS_INFO[stem]
    branch_yomi, animal = cd.BRANCHES_INFO[branch]
    return {
        "name": stem + branch,
        "yomi": stem_yomi + branch_yomi,
        "desc": cd.KANSHI_DESC.format(stem=stem, stem_yomi=stem_yomi, gogyo=gogyo, inyo=inyo,
                                      branch=branch, branch_yomi=branch_yomi, animal=animal),
        "note": cd.KANSHI_NOTE,
    }


def day_branch(d: date) -> str:
    return BRANCHES[kanshi_index(d) % 12]


def day_stem(d: date) -> str:
    return STEMS[kanshi_index(d) % 10]


# ------------------------------------------------------------------
# 六曜
# ------------------------------------------------------------------
def rokuyo_name(kyureki_month: int, kyureki_day: int) -> str:
    """旧暦の月と日の和を6で割った余りで決まる(閏月は同じ月番号として扱う)"""
    return cd.ROKUYO_ORDER[(kyureki_month + kyureki_day) % 6]


def rokuyo_info(kyureki_month: int, kyureki_day: int) -> dict:
    name = rokuyo_name(kyureki_month, kyureki_day)
    info = cd.ROKUYO[name]
    return {"name": name, "yomi": info["yomi"], "timing": info["timing"], "desc": info["desc"]}


# ------------------------------------------------------------------
# 太陽黄経が特定の値になる日(日本時間の日付)
# ------------------------------------------------------------------
@lru_cache(maxsize=None)
def crossing_date(year: int, lon: int) -> date:
    start = datetime(year, 1, 1, tzinfo=JST).astimezone(timezone.utc)
    t = find_longitude_crossing(lon, start, search_days=366)
    return t.astimezone(JST).date()


def risshun(year): return crossing_date(year, 315)
def shunbun(year): return crossing_date(year, 0)
def shubun(year): return crossing_date(year, 180)
def toji(year): return crossing_date(year, 270)


# ------------------------------------------------------------------
# 雑節
# ------------------------------------------------------------------
def _nearest_tsuchinoe(center: date) -> date:
    """中心の日に最も近い戊の日。前後が同じ距離のときは前の日を採る。"""
    best = None
    for k in range(-5, 6):
        d = center + timedelta(days=k)
        if day_stem(d) == "戊":
            if best is None or abs(k) < abs((best - center).days):
                best = d
    return best


@lru_cache(maxsize=None)
def zassetsu_in_year(year: int) -> dict:
    """その年の雑節を {date: [name, ...]} で返す。(節分は年中行事側で扱う)"""
    res = {}

    def add(d, name):
        res.setdefault(d, []).append(name)

    rs = risshun(year)
    sh, sb = shunbun(year), shubun(year)
    add(sh - timedelta(days=3), "彼岸入り"); add(sh, "彼岸の中日"); add(sh + timedelta(days=3), "彼岸明け")
    add(sb - timedelta(days=3), "彼岸入り"); add(sb, "彼岸の中日"); add(sb + timedelta(days=3), "彼岸明け")
    add(_nearest_tsuchinoe(sh), "社日"); add(_nearest_tsuchinoe(sb), "社日")
    add(rs + timedelta(days=87), "八十八夜")
    add(crossing_date(year, 80), "入梅")
    add(crossing_date(year, 100), "半夏生")
    add(rs + timedelta(days=209), "二百十日")
    add(rs + timedelta(days=219), "二百二十日")

    # 土用: 入り=太陽黄経27°/117°/207°/297°の日、明け=立夏・立秋・立冬・立春の前日
    doyo = [
        ("春", crossing_date(year, 27),  crossing_date(year, 45) - timedelta(days=1)),
        ("夏", crossing_date(year, 117), crossing_date(year, 135) - timedelta(days=1)),
        ("秋", crossing_date(year, 207), crossing_date(year, 225) - timedelta(days=1)),
        ("冬", crossing_date(year, 297), rs - timedelta(days=1)),
    ]
    for season, start, end in doyo:
        add(start, "土用入り"); add(end, "土用明け")
        ushi = [start + timedelta(days=i) for i in range((end - start).days + 1)
                if day_branch(start + timedelta(days=i)) == "丑"]
        for n, d in enumerate(ushi, 1):
            label = "土用の丑の日" if season == "夏" else f"{season}の土用の丑の日"
            if len(ushi) > 1:
                label += "（一の丑）" if n == 1 else "（二の丑）"
            add(d, label)
    return res


def zassetsu_on(d: date) -> list:
    out = []
    for name in zassetsu_in_year(d.year).get(d, []):
        key = name.split("（")[0]
        if key.endswith("の土用の丑の日") and key != "土用の丑の日":
            key = "土用の丑の日"
        out.append({"category": "雑節", "name": name, "desc": cd.ZASSETSU.get(key, "")})
    return out


# ------------------------------------------------------------------
# 一粒万倍日
# ------------------------------------------------------------------
def setsu_month(d: date) -> int:
    """節月(立春=1 ... 小寒=12)。節入り当日から新しい月とする。"""
    return cd.SEKKI_TO_SETSU_MONTH[get_sekki_and_kou(d)["sekki_name"]]


def is_ichiryu_manbai(d: date) -> bool:
    return day_branch(d) in cd.ICHIRYU_MANBAI_BRANCHES[setsu_month(d)]


# ------------------------------------------------------------------
# 選日(天赦日・寅の日・巳の日・己巳の日・不成就日)
# ------------------------------------------------------------------
def _setsu_season(d: date) -> str:
    m = setsu_month(d)
    return "春" if m <= 3 else "夏" if m <= 6 else "秋" if m <= 9 else "冬"


def is_tenshanichi(d: date) -> bool:
    return kanshi_name(d) == cd.TENSHANICHI_KANSHI[_setsu_season(d)]


def is_fujojubi(kyureki_month: int, kyureki_day: int) -> bool:
    return kyureki_day in cd.FUJOJUBI_DAYS[kyureki_month]


def senjitsu_on(d: date, kyureki_month: int, kyureki_day: int) -> list:
    """その日の選日(天赦日・寅の日・巳の日・己巳の日・不成就日)。一粒万倍日は別に扱う。"""
    names = []
    if is_tenshanichi(d):
        names.append("天赦日")
    if day_branch(d) == "寅":
        names.append("寅の日")
    if day_branch(d) == "巳":
        names.append("己巳の日" if kanshi_name(d) == "己巳" else "巳の日")
    if is_fujojubi(kyureki_month, kyureki_day):
        names.append("不成就日")
    return [{"category": "選日", "name": n, "desc": cd.SENJITSU_DESC[n]} for n in names]


# ------------------------------------------------------------------
# 国民の祝日
# ------------------------------------------------------------------
def _nth_weekday(year, month, weekday, n) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


@lru_cache(maxsize=None)
def holidays_in_year(year: int) -> dict:
    """{date: (名称, 種別)}。種別は 祝日 / 振替休日 / 国民の休日"""
    base = {}
    for (m, dd), name in cd.FIXED_HOLIDAYS.items():
        base[date(year, m, dd)] = name
    for name, (m, n) in cd.HAPPY_MONDAY.items():
        base[_nth_weekday(year, m, 0, n)] = name
    base[shunbun(year)] = "春分の日"
    base[shubun(year)] = "秋分の日"

    result = {d: (name, "祝日") for d, name in base.items()}

    # 振替休日: 祝日が日曜日のとき、その後で最も近い「祝日でない日」
    for h in sorted(base):
        if h.weekday() == 6:
            d = h + timedelta(days=1)
            while d in base or d in result:
                d += timedelta(days=1)
            result[d] = ("振替休日", "振替休日")

    # 国民の休日: 前日と翌日がともに祝日の平日(日曜日・振替休日を除く)
    d = date(year, 1, 2)
    while d.year == year:
        if d not in result and d.weekday() != 6:
            if (d - timedelta(days=1)) in base and (d + timedelta(days=1)) in base:
                result[d] = ("国民の休日", "国民の休日")
        d += timedelta(days=1)
    return result


def holidays_on(d: date) -> list:
    h = holidays_in_year(d.year).get(d)
    if not h:
        return []
    name, kind = h
    return [{"category": "国民の祝日", "name": name, "kind": kind, "desc": cd.HOLIDAY_DESC.get(name, "")}]


# ------------------------------------------------------------------
# 朔(新月)の日付 → 旧暦の十五夜・十三夜
# ------------------------------------------------------------------
def _new_moon_jst_date_on_or_before(d: date) -> date:
    end = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=JST).astimezone(timezone.utc)
    nm = ephem.previous_new_moon(end).datetime().replace(tzinfo=timezone.utc)
    return nm.astimezone(JST).date()


@lru_cache(maxsize=None)
def jugoya(year: int) -> date:
    """十五夜(旧暦8月15日)。旧暦8月は秋分を含む月なので、秋分日が属する月の朔日+14日。"""
    return _new_moon_jst_date_on_or_before(shubun(year)) + timedelta(days=14)


@lru_cache(maxsize=None)
def jusanya(year: int) -> date:
    """十三夜(旧暦9月13日)。旧暦9月は霜降を含む月なので、霜降日が属する月の朔日+12日。"""
    return _new_moon_jst_date_on_or_before(crossing_date(year, 210)) + timedelta(days=12)


# ------------------------------------------------------------------
# 年中行事・記念日 (固定日は memorial_days.jsonl、規則で決まるものはここで計算)
# ------------------------------------------------------------------
@lru_cache(maxsize=None)
def _load_fixed_entries():
    path = os.path.join(SCRIPT_DIR, "memorial_days.jsonl")
    db = {}
    if not os.path.exists(path):
        return db
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                db[(rec["month"], rec["day"])] = rec["entries"]
    return db


def _rule_events(d: date) -> list:
    """規則で日付が決まる年中行事: [(名称, major)]"""
    out = []
    y = d.year
    if d == risshun(y) - timedelta(days=1):
        out.append(("節分", True))
    if d.month == 2 and day_branch(d) == "午" and d.day <= 12:
        out.append(("初午", True))          # 2月最初の午の日(最初の午の日は必ず12日以内)
    if (d.month, d.day) == (8, 13):
        out.append(("お盆(盆入り)", True))
    if (d.month, d.day) == (8, 16):
        out.append(("お盆(送り火)", False))
    if d == jugoya(y):
        out.append(("十五夜(中秋の名月)", True))
    if d == jusanya(y):
        out.append(("十三夜", True))
    if d == toji(y):
        out.append(("冬至", True))
    if d.month == 11 and day_branch(d) == "酉":
        n = (d.day - 1) // 12 + 1
        out.append((f"酉の市（{'一二三'[n - 1]}の酉）", False))
    return out


def events_on(d: date) -> list:
    out = []
    for e in _load_fixed_entries().get((d.month, d.day), []):
        if e.get("category") == "年中行事":
            out.append({"category": "年中行事", "name": e["name"], "desc": e["origin"], "major": bool(e.get("major"))})
    for name, major in _rule_events(d):
        key = name.split("（")[0]
        out.append({"category": "年中行事", "name": name, "desc": cd.EVENT_DESC.get(key, ""), "major": major})
    return out


def kinenbi_on(d: date) -> list:
    return [{"category": "記念日", "name": e["name"], "desc": e["origin"]}
            for e in _load_fixed_entries().get((d.month, d.day), [])
            if e.get("category", "記念日") == "記念日"]


# ------------------------------------------------------------------
# 重要な祭日
# ------------------------------------------------------------------
def saijitsu_on(d: date) -> list:
    out = [{"category": "重要な祭日", "name": n, "desc": desc}
           for n, desc in cd.SAIJITSU_FIXED.get((d.month, d.day), [])]
    if d == shunbun(d.year):
        n, desc = cd.SAIJITSU_EQUINOX["春分"]; out.append({"category": "重要な祭日", "name": n, "desc": desc})
    if d == shubun(d.year):
        n, desc = cd.SAIJITSU_EQUINOX["秋分"]; out.append({"category": "重要な祭日", "name": n, "desc": desc})
    return out


# ------------------------------------------------------------------
# まとめ
# ------------------------------------------------------------------
def day_calendar_info(d: date, kyureki: dict = None) -> dict:
    if kyureki is None:
        from koyomi_engine import compute_kyuureki
        kyureki = compute_kyuureki(d)
    ichi = is_ichiryu_manbai(d)
    return {
        "kanshi": kanshi_name(d),
        "ichiryu_manbai": ({"name": "一粒万倍日", "desc": cd.ICHIRYU_MANBAI_DESC} if ichi else None),
        "senjitsu": senjitsu_on(d, kyureki["kyureki_month"], kyureki["kyureki_day"]),
        "zassetsu": zassetsu_on(d),
        "holidays": holidays_on(d),
        "events": events_on(d),
        "saijitsu": saijitsu_on(d),
        "kinenbi": kinenbi_on(d),
    }


def notification_items(info: dict) -> list:
    """通知のきっかけになる項目(国民の祝日 → 重要な祭日 → 主要な年中行事 → 記念日の順)。
    雑節・選日・一粒万倍日は、ここではなく render_koyomi.build_reasons() で、
    calendar_data.py の設定(NOTIFY_ZASSETSU など)に従って加える。六曜は通知のきっかけにしない。"""
    items = []
    items += info["holidays"]
    items += info["saijitsu"]
    items += [e for e in info["events"] if e.get("major")]
    items += info["kinenbi"]
    return items
