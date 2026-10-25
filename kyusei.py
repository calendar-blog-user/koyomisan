"""九星気学(日の九星・月の九星・年の九星)の計算

- 年の九星: 立春で切り替わる。2000年=九紫、2001年=八白…と、1年ごとに1つずつ戻る
- 月の九星: 節入り(立春・啓蟄・清明…)で切り替わる。年の十二支ごとに、寅月(立春〜)の星が決まり、月ごとに1つずつ戻る
    子・午・卯・酉の年=寅月が八白 / 辰・戌・丑・未の年=寅月が五黄 / 寅・申・巳・亥の年=寅月が二黒
- 日の九星(日家九星): 冬至に最も近い甲子の日から、一白→二黒…と順に進み(陽遁)、
    夏至に最も近い甲子の日から、九紫→八白…と逆に進む(陰遁)。次の冬至に最も近い甲子の日で、また陽遁になる。
  流派によって計算方法が異なる。ここでは、いちばん広く使われている方法を使う。
"""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import calendar_data as cd
import calendar_extras as ce
from koyomi_engine import find_longitude_crossing, JST

# 節入り(月の九星が切り替わる日)。黄経 → 目安の月日(探索の起点にだけ使う)
_SETSU = [(315, 2, 4), (345, 3, 6), (15, 4, 5), (45, 5, 6), (75, 6, 6), (105, 7, 7),
          (135, 8, 7), (165, 9, 8), (195, 10, 8), (225, 11, 7), (255, 12, 7), (285, 1, 5)]
_YOUTOU_LON, _INTOU_LON = 270, 90   # 冬至・夏至の太陽黄経


def _crossing_date(lon: float, y: int, m: int, d: int) -> date:
    """太陽黄経が lon になる日(日本時間の日付)。y年m月d日の10日前から探す"""
    start = (datetime(y, m, d, tzinfo=JST) - timedelta(days=10)).astimezone(timezone.utc)
    return find_longitude_crossing(lon, start, search_days=40).astimezone(JST).date()


@lru_cache(maxsize=None)
def setsuiri_dates(year: int) -> tuple:
    """year年に始まる、12個の節入りの日付(立春=寅月から小寒=丑月まで)。丑月は翌年1月になる"""
    out = []
    for lon, m, d in _SETSU:
        y = year + 1 if m == 1 else year        # 小寒(1月)は、次の年の1月
        out.append(_crossing_date(lon, y, m, d))
    return tuple(out)


def _nearest_kinoe_ne(d: date) -> date:
    """d に最も近い甲子の日(同じ近さなら前のほう)"""
    i = ce.kanshi_index(d)                       # 甲子=0
    before = d - timedelta(days=i)
    after = before + timedelta(days=60)
    return before if (d - before) <= (after - d) else after


@lru_cache(maxsize=None)
def _dun_starts(year: int) -> tuple:
    """year年の前後で、陽遁・陰遁が始まる日。[(開始日, "陽遁"/"陰遁"), ...] を日付順に返す"""
    items = []
    for y in (year - 1, year, year + 1):
        items.append((_nearest_kinoe_ne(_crossing_date(_YOUTOU_LON, y, 12, 22)), "陽遁"))
        items.append((_nearest_kinoe_ne(_crossing_date(_INTOU_LON, y, 6, 21)), "陰遁"))
    return tuple(sorted(items))


def day_star_number(d: date) -> int:
    """日の九星の番号(1〜9)"""
    starts = [s for s in _dun_starts(d.year) if s[0] <= d]
    start, kind = starts[-1]
    k = (d - start).days
    return (k % 9) + 1 if kind == "陽遁" else 9 - (k % 9)


def dun_kind(d: date) -> str:
    """その日が陽遁・陰遁のどちらか"""
    return [s for s in _dun_starts(d.year) if s[0] <= d][-1][1]


def setsu_year(d: date) -> int:
    """立春で切り替わる「節年」(1月1日〜立春の前日は、前の年)"""
    return d.year if d >= setsuiri_dates(d.year)[0] else d.year - 1


def year_star_number(d: date) -> int:
    n = 11 - (setsu_year(d) % 9)
    return n - 9 if n > 9 else n


def month_index(d: date) -> int:
    """節月の番号(0=寅月〜11=丑月)"""
    y = setsu_year(d)
    dates = setsuiri_dates(y)
    return max(i for i, s in enumerate(dates) if s <= d)


def month_star_number(d: date) -> int:
    branch = (setsu_year(d) - 4) % 12             # 子=0
    start = {0: 8, 6: 8, 3: 8, 9: 8, 4: 5, 10: 5, 1: 5, 7: 5, 2: 2, 8: 2, 5: 2, 11: 2}[branch]
    n = start - month_index(d)
    while n <= 0:
        n += 9
    return n


def kyusei_info(d: date) -> dict:
    """サイトに出す九星の情報(日・月・年)"""
    def star(n):
        name, yomi, gogyo, direction, imagery, _ = cd.KYUSEI[n]
        return {"number": n, "name": name, "yomi": yomi, "gogyo": gogyo, "direction": direction, "imagery": imagery}
    dn = day_star_number(d)
    return {
        "day": {**star(dn), "desc": cd.KYUSEI[dn][5], "dun": dun_kind(d)},
        "month": star(month_star_number(d)),
        "year": star(year_star_number(d)),
        "note": cd.KYUSEI_NOTE,
    }
