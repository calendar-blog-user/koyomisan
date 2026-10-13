"""
天文イベント: 月相(朔・上弦・望・下弦)、日食・月食、流星群の極大。

  ・月相       : 天文計算(ephem)。国立天文台 暦要項(2026・2027年の朔弦望)と照合して方式を決めている。
  ・日食・月食 : 国立天文台の公表一覧(「日本で見られる」もの)を、データとして保持している。
                 毎年2月ごろに発表される暦要項に合わせて、ECLIPSES を更新すること。
  ・流星群     : IMOが定める極大の太陽黄経から、極大日時を計算する。国立天文台の2026年の公表値と照合済み。
"""
import math
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import ephem

from koyomi_engine import find_longitude_crossing

JST = timezone(timedelta(hours=9))
UTC = timezone.utc
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]

# ------------------------------------------------------------------
# 月相(朔弦望)
# ------------------------------------------------------------------
PHASES = [("朔", ephem.next_new_moon), ("上弦", ephem.next_first_quarter_moon),
          ("望", ephem.next_full_moon), ("下弦", ephem.next_last_quarter_moon)]
PHASE_LABEL = {"朔": "新月（朔）", "上弦": "上弦", "望": "満月（望）", "下弦": "下弦"}
# ephemの月相の時刻は、国立天文台の公表値より平均4秒ほど早い。分未満を四捨五入するときの境界で
# 1分ずれることがあるため、4秒を補正する(暦要項2026・2027年の朔弦望99件のうち、補正なしは91件、補正ありは98件が一致。
# 補正値は、2026年だけで決めても2027年が、2027年だけで決めても2026年が、同じ+4秒で最良になることを確認済み)。
PHASE_TIME_CORRECTION_SEC = 4


@lru_cache(maxsize=None)
def phase_events_year(year: int) -> tuple:
    """その年(日本時間)の朔・上弦・望・下弦を ((種類, 日本時間のdatetime[分未満四捨五入]), ...) で返す"""
    start = datetime(year, 1, 1, tzinfo=JST)
    end = datetime(year + 1, 1, 1, tzinfo=JST)
    out = []
    for kind, fn in PHASES:
        t = (start - timedelta(days=40)).astimezone(UTC)
        while True:
            e = fn(t)
            exact = e.datetime().replace(tzinfo=UTC).astimezone(JST) + timedelta(seconds=PHASE_TIME_CORRECTION_SEC)
            rounded = (exact + timedelta(seconds=30)).replace(second=0, microsecond=0)
            if rounded >= end:
                break
            if rounded >= start:
                out.append((kind, rounded))
            t = e.datetime().replace(tzinfo=UTC) + timedelta(days=1)
    return tuple(sorted(out, key=lambda x: x[1]))


def _fmt_dt(dt: datetime) -> str:
    return f"{dt.month}月{dt.day}日({WEEKDAY_JP[dt.weekday()]}) {dt.hour}:{dt.minute:02d}"


def phases_on(d: date) -> list:
    return [{"kind": k, "label": PHASE_LABEL[k], "time": f"{dt.hour}:{dt.minute:02d}"}
            for k, dt in phase_events_year(d.year) if dt.date() == d]


def next_phase_after(d: date, kind: str):
    """その日より後(翌日以降)の、次の朔/望などの日時"""
    for y in (d.year, d.year + 1):
        for k, dt in phase_events_year(y):
            if k == kind and dt.date() > d:
                return dt
    return None


# ------------------------------------------------------------------
# 日食・月食 (日本で見られるもの。国立天文台の一覧・暦要項による)
#   date は食の最大の日付(日本時間)。
# ------------------------------------------------------------------
ECLIPSES = [
    {"date": date(2026, 3, 3), "kind": "皆既月食",
     "summary": "日本全国で皆既食が見られます。",
     "detail": "東京では、食の始め18:50、皆既の始め20:04、食の最大20:34(食分1.16)、皆既の終わり21:03、食の終わり22:18です。"},
    {"date": date(2028, 7, 7), "kind": "部分月食",
     "summary": "日本で見られます。明け方、月が欠けたまま沈む「月入帯食」です。", "detail": ""},
    {"date": date(2029, 1, 1), "kind": "皆既月食",
     "summary": "日本全国で見られます。元日の皆既月食です。", "detail": ""},
    {"date": date(2029, 12, 21), "kind": "皆既月食",
     "summary": "日本で見られますが、多くの地域では皆既になる前に月が沈む「月入帯食」です。", "detail": ""},
    {"date": date(2030, 6, 1), "kind": "金環日食",
     "summary": "北海道で金環日食、そのほかの全国で部分日食が見られます。日本で見られる日食は、2023年以来です。", "detail": ""},
    {"date": date(2030, 6, 16), "kind": "部分月食",
     "summary": "日本で見られます。月が欠けたまま沈む「月入帯食」です。", "detail": ""},
]
ECLIPSE_LIST_VALID_UNTIL = date(2030, 12, 31)   # この日までの一覧(国立天文台の月食一覧は2030年まで)


def eclipses_on(d: date) -> list:
    return [e for e in ECLIPSES if e["date"] == d]


def next_eclipse_after(d: date):
    for e in ECLIPSES:
        if e["date"] > d:
            return e
    return None


# ------------------------------------------------------------------
# 流星群 (極大の太陽黄経: IMO、J2000.0分点)
# ------------------------------------------------------------------
SHOWERS = [
    {"name": "しぶんぎ座流星群", "lon": 283.15,
     "desc": "三大流星群の一つ。活動が活発な期間が短く、年によって流星の数が大きく変わります。放射点が高くなる明け方が見頃です。"},
    {"name": "4月こと座流星群", "lon": 32.32,
     "desc": "毎年見られる流星群で、紀元前687年に中国で観測されたのが最初の記録とされるほど、歴史の古い流星群です。普段の年は、流星の数は多くありません。"},
    {"name": "みずがめ座η流星群", "lon": 45.5,
     "desc": "ハレー彗星を母天体とする流星群。日本では放射点が昇るのが遅く、明け方の短い時間が見頃です。"},
    {"name": "ペルセウス座流星群", "lon": 140.0,
     "desc": "三大流星群の一つで、毎年お盆のころに見られます。母天体はスイフト・タットル彗星です。"},
    {"name": "10月りゅう座流星群", "lon": 195.4,
     "desc": "「ジャコビニ流星群」の名でも知られ、母天体はジャコビニ・ツィナー彗星です。普段は流星が少ない一方、突然活発になる年があります。"},
    {"name": "オリオン座流星群", "lon": 208.0,
     "desc": "ハレー彗星を母天体とする流星群。流星の速度が速く、明るい流星が多いのが特徴です。"},
    {"name": "しし座流星群", "lon": 235.27,
     "desc": "母天体はテンペル・タットル彗星。約33年ごとに、流星が雨のように降る「流星雨」が起こることで知られます。"},
    {"name": "ふたご座流星群", "lon": 262.2,
     "desc": "三大流星群の一つで、年間で最大級の流星群です。母天体は小惑星(3200)ファエトンです。"},
    {"name": "こぐま座流星群", "lon": 270.7,
     "desc": "12月下旬に活動する流星群で、母天体はタットル彗星です。流星の数は多くありません。"},
]
PRECESSION_DEG_PER_YEAR = 0.013969   # 歳差: J2000.0分点 → その時点の分点(年あたり約50.29秒角)


@lru_cache(maxsize=None)
def meteor_peaks(year: int) -> tuple:
    """その年の各流星群の極大(日本時間)を、(流星群のdict, 極大のdatetime)の組で返す。
    国立天文台の公表値(IMOの予報)と同じく「時」までを意味のある精度として扱う。"""
    out = []
    for sh in SHOWERS:
        t = year + 0.5
        tc = None
        for _ in range(3):   # 歳差は極大の時期に依存するので、数回の反復で収束させる
            target = (sh["lon"] + PRECESSION_DEG_PER_YEAR * (t - 2000.0)) % 360
            start = datetime(year, 1, 1, tzinfo=JST).astimezone(UTC)
            tc = find_longitude_crossing(target, start, search_days=366).astimezone(JST)
            t = year + (tc - datetime(year, 1, 1, tzinfo=JST)).total_seconds() / (365.25 * 86400)
        out.append((sh, tc))
    return tuple(out)


def _round_hour(dt: datetime) -> datetime:
    return (dt + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)


def meteor_peak_rounded(year: int, name: str) -> datetime:
    for sh, tc in meteor_peaks(year):
        if sh["name"] == name:
            return _round_hour(tc)
    raise KeyError(name)


def meteors_on(d: date) -> list:
    """その日が極大日(極大の日時を「時」に丸めたときの日付)の流星群"""
    res = []
    for sh, tc in meteor_peaks(d.year):
        pk = _round_hour(tc)
        if pk.date() == d:
            res.append((sh, pk))
    return res


def next_meteor_after(d: date):
    for y in (d.year, d.year + 1):
        peaks = sorted(((_round_hour(tc), sh) for sh, tc in meteor_peaks(y)), key=lambda x: x[0])
        for pk, sh in peaks:
            if pk.date() > d:
                return sh, pk
    return None


def moon_condition_text(peak: datetime, lat=35.65, lon=139.7333) -> str:
    """極大の夜の「月明かり」を、見頃の時間帯(3時頃・日本時間)の月の位置から判断して一文で返す(東京の場合)。"""
    view_day = peak.date() + (timedelta(days=1) if peak.hour >= 20 else timedelta(0))
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.elevation = 0
    obs.pressure = 0
    obs.date = datetime(view_day.year, view_day.month, view_day.day, 3, 0, 0, tzinfo=JST).astimezone(UTC)
    moon = ephem.Moon(obs)
    alt = math.degrees(float(moon.alt))
    illum = float(moon.phase)   # 輝面率(%)
    if alt <= 0:
        return "見頃の3時ごろには月が沈んでいて、月明かりの影響はありません。"
    if illum < 30:
        return f"3時ごろの月は細く（輝面率{illum:.0f}%）、月明かりの影響は小さそうです。"
    return f"3時ごろは月が空にあり（輝面率{illum:.0f}%）、暗い流星は見えにくくなります。月を視界から外して観察しましょう。"


# ------------------------------------------------------------------
# まとめ: 「月や星の暦・天文情報」に載せる内容
# ------------------------------------------------------------------
def astro_summary(d: date) -> dict:
    items, tags = [], []

    # --- 月の満ち欠け ---
    lines = []
    for p in phases_on(d):
        lines.append(f"今日は{p['label']}です（{p['time']}）。")
        tags.append(f"{p['label'].split('（')[0]} {p['time']}")
    nn, nf = next_phase_after(d, "朔"), next_phase_after(d, "望")
    if nn:
        lines.append(f"次の新月：{_fmt_dt(nn)}")
    if nf:
        lines.append(f"次の満月：{_fmt_dt(nf)}")
    items.append({"title": "月の満ち欠け", "lines": lines})

    # --- 日食・月食 ---
    lines = []
    for e in eclipses_on(d):
        lines.append(f"今日は{e['kind']}です。{e['summary']}{e['detail']}")
        tags.append(e["kind"])
    tomorrow = d + timedelta(days=1)
    for e in eclipses_on(tomorrow):
        lines.append(f"明日は{e['kind']}です。{e['summary']}")
    ne = next_eclipse_after(d)
    if ne:
        lines.append(f"次に日本で見られる日食・月食：{ne['date'].year}年{ne['date'].month}月{ne['date'].day}日 {ne['kind']}（{ne['summary']}）")
    else:
        lines.append(f"国立天文台の一覧にある、日本で見られる日食・月食は{ECLIPSE_LIST_VALID_UNTIL.year}年までです。")
    items.append({"title": "日食・月食", "lines": lines})

    # --- 流星群 ---
    lines = []
    for sh, pk in meteors_on(d):
        lines.append(f"今日は{sh['name']}の極大日です（極大は{pk.hour}時ごろ）。{sh['desc']}")
        lines.append(moon_condition_text(pk))
        tags.append(f"{sh['name'].replace('流星群', '')}流星群 極大")
    for sh, pk in meteors_on(tomorrow):
        lines.append(f"明日は{sh['name']}の極大日です（極大は{pk.hour}時ごろ）。")
    nm = next_meteor_after(d)
    if nm:
        sh, pk = nm
        lines.append(f"次の流星群：{sh['name']}（極大は{pk.month}月{pk.day}日({WEEKDAY_JP[pk.weekday()]}) {pk.hour}時ごろ）")
    items.append({"title": "流星群", "lines": lines})
    return {"items": items, "tags": tags}
