"""
日の出・日の入り・日南中、月の出・月の入り・月南中を地点ごとに計算するモジュール。

計算の方式は国立天文台 暦計算室「今日のこよみ」の値と照合して決めている:
  - 太陽: 上端が地平線に接する時刻(大気差35′を考慮)
  - 月  : 中心が地平線(大気差35′を考慮)に達する時刻
  - 時刻は分単位に四捨五入(日本標準時)
東京・岡山の公表値および暦要項(東京の日出入)と突き合わせ、概ね±1分以内で一致することを確認している。
"""
import math
from datetime import datetime, timedelta, timezone

import ephem

JST = timezone(timedelta(hours=9))

# 政令指定都市(20市)＋東京。緯度経度は市役所(都庁)付近の値。
# id は Firestore に保存するキー(英数字)。表示名は name。
CITIES = [
    {"id": "tokyo",      "name": "東京",     "pref": "東京都",   "lat": 35.6500, "lon": 139.7333},  # 国立天文台の「東京」(北緯35°39′ 東経139°44′)に合わせる
    {"id": "sapporo",    "name": "札幌市",   "pref": "北海道",   "lat": 43.0642, "lon": 141.3469},
    {"id": "sendai",     "name": "仙台市",   "pref": "宮城県",   "lat": 38.2682, "lon": 140.8694},
    {"id": "saitama",    "name": "さいたま市", "pref": "埼玉県",  "lat": 35.8617, "lon": 139.6455},
    {"id": "chiba",      "name": "千葉市",   "pref": "千葉県",   "lat": 35.6073, "lon": 140.1063},
    {"id": "yokohama",   "name": "横浜市",   "pref": "神奈川県", "lat": 35.4437, "lon": 139.6380},
    {"id": "kawasaki",   "name": "川崎市",   "pref": "神奈川県", "lat": 35.5309, "lon": 139.7030},
    {"id": "sagamihara", "name": "相模原市", "pref": "神奈川県", "lat": 35.5714, "lon": 139.3733},
    {"id": "niigata",    "name": "新潟市",   "pref": "新潟県",   "lat": 37.9162, "lon": 139.0364},
    {"id": "shizuoka",   "name": "静岡市",   "pref": "静岡県",   "lat": 34.9756, "lon": 138.3828},
    {"id": "hamamatsu",  "name": "浜松市",   "pref": "静岡県",   "lat": 34.7108, "lon": 137.7261},
    {"id": "nagoya",     "name": "名古屋市", "pref": "愛知県",   "lat": 35.1815, "lon": 136.9066},
    {"id": "kyoto",      "name": "京都市",   "pref": "京都府",   "lat": 35.0116, "lon": 135.7681},
    {"id": "osaka",      "name": "大阪市",   "pref": "大阪府",   "lat": 34.6937, "lon": 135.5023},
    {"id": "sakai",      "name": "堺市",     "pref": "大阪府",   "lat": 34.5733, "lon": 135.4830},
    {"id": "kobe",       "name": "神戸市",   "pref": "兵庫県",   "lat": 34.6913, "lon": 135.1830},
    {"id": "okayama",    "name": "岡山市",   "pref": "岡山県",   "lat": 34.6551, "lon": 133.9195},
    {"id": "hiroshima",  "name": "広島市",   "pref": "広島県",   "lat": 34.3853, "lon": 132.4553},
    {"id": "kitakyushu", "name": "北九州市", "pref": "福岡県",   "lat": 33.8834, "lon": 130.8752},
    {"id": "fukuoka",    "name": "福岡市",   "pref": "福岡県",   "lat": 33.5904, "lon": 130.4017},
    {"id": "kumamoto",   "name": "熊本市",   "pref": "熊本県",   "lat": 32.8032, "lon": 130.7079},
]
CITY_BY_ID = {c["id"]: c for c in CITIES}
DEFAULT_CITY_ID = "tokyo"


def _observer(lat, lon):
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)
    obs.elevation = 0
    obs.pressure = 0          # 屈折は horizon 側で与える(標準大気差35′)
    obs.horizon = "-0:35"
    return obs


def _fmt(t_utc):
    """UTCのdatetimeを、日本時間の「H:MM」(分未満四捨五入)に整形する"""
    j = t_utc.astimezone(JST) + timedelta(seconds=30)
    return f"{j.hour}:{j.minute:02d}"


def _event(obs, body_factory, method, day_start_utc, day_end_utc, **kw):
    obs.date = day_start_utc
    try:
        t = getattr(obs, method)(body_factory(), **kw).datetime().replace(tzinfo=timezone.utc)
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        return None
    return t if t < day_end_utc else None


def sun_moon_times(target_date, lat, lon):
    """
    指定日(日本時間の暦日)の、日の出・日南中・日の入り・月の出・月南中・月の入りを返す。
    その日のうちに起こらない場合は None。
    """
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=JST).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    obs = _observer(lat, lon)

    raw = {
        "sunrise":      _event(obs, ephem.Sun,  "next_rising",  start, end),
        "solar_noon":   _event(obs, ephem.Sun,  "next_transit", start, end),
        "sunset":       _event(obs, ephem.Sun,  "next_setting", start, end),
        "moonrise":     _event(obs, ephem.Moon, "next_rising",  start, end, use_center=True),
        "moon_transit": _event(obs, ephem.Moon, "next_transit", start, end),
        "moonset":      _event(obs, ephem.Moon, "next_setting", start, end, use_center=True),
    }
    return {k: (_fmt(v) if v else None) for k, v in raw.items()}


def sun_moon_for_all_cities(target_date):
    return {c["id"]: sun_moon_times(target_date, c["lat"], c["lon"]) for c in CITIES}


DIRECTIONS_8 = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"]


def _tomin(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def moon_tonight_text(target_date, lat, lon, times, hour=20):
    """
    その日の夜(hour時 JST)に、月がどの方角・どのくらいの高さに見えるかを、日本語の一文で返す。
    月が地平線の下にある場合は、同じ表(times)の月の出・月の入り時刻を使って案内する
    (表と文章で時刻がずれないようにするため)。
    """
    obs = _observer(lat, lon)
    obs.date = datetime(target_date.year, target_date.month, target_date.day, hour, 0, 0,
                        tzinfo=JST).astimezone(timezone.utc)
    moon = ephem.Moon(obs)
    alt = math.degrees(float(moon.alt))
    az = math.degrees(float(moon.az))

    if alt > 0:
        direction = DIRECTIONS_8[int(((az + 22.5) % 360) // 45)]
        height = "空高く" if alt > 50 else ("ほどよい高さに" if alt > 20 else "低い位置に")
        return f"今夜{hour}時頃には、{direction}の空の{height}月が見えています。"

    rise, mset = times.get("moonrise"), times.get("moonset")
    if rise and _tomin(rise) > hour * 60:
        return f"月の出は{rise}頃で、{hour}時頃はまだ地平線の下にあります。夜更けに昇ってきます。"
    if mset and _tomin(mset) <= hour * 60:
        return f"月は{mset}頃に沈むため、{hour}時頃にはもう夜空に見えません。"
    return f"{hour}時頃、月は地平線の下にあります。"


# ------------------------------------------------------------------
# 昼の長さ(日の出から日の入りまで)と、前日との差
# ------------------------------------------------------------------
def _sun_rise_set_exact(target_date, lat, lon):
    """分に丸める前の、日の出・日の入りの時刻(UTC)"""
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=JST).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    obs = _observer(lat, lon)
    rise = _event(obs, ephem.Sun, "next_rising", start, end)
    sset = _event(obs, ephem.Sun, "next_setting", start, end)
    return rise, sset


def day_length_seconds(target_date, lat, lon):
    rise, sset = _sun_rise_set_exact(target_date, lat, lon)
    if not rise or not sset:
        return None
    return (sset - rise).total_seconds()


def day_length_fields(target_date, lat, lon) -> dict:
    """昼の長さ(分に丸めた表記)と、前日との差(秒)を返す。日の出・日の入りが無い地点は想定しない。"""
    today = day_length_seconds(target_date, lat, lon)
    prev = day_length_seconds(target_date - timedelta(days=1), lat, lon)
    if today is None or prev is None:
        return {"day_length": None, "day_diff": None}
    minutes = int(today // 60 + (1 if today % 60 >= 30 else 0))   # 四捨五入
    label = f"{minutes // 60}時間{minutes % 60:02d}分"
    diff = today - prev
    if abs(diff) < 5:
        diff_label = "前日とほぼ同じ長さ"
    else:
        m, s = divmod(int(round(abs(diff))), 60)
        amount = f"{m}分{s:02d}秒" if m else f"{s}秒"
        diff_label = f"前日より{amount}{'長い' if diff > 0 else '短い'}"
    return {"day_length": label, "day_diff": diff_label, "day_diff_seconds": round(diff, 1)}
