"""
こよみ計算エンジン プロトタイプ
- 二十四節気 / 七十二候 / 月齢 / 旧暦(太陰太陽暦) を算出する
- LLMは使わず、ephem(天文計算)のみで決定的に計算する
"""

import ephem
import math
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# ---------------------------------------------------------
# 二十四節気（黄経0,15,30...345度に対応。0度=春分 を基準に定義）
# ---------------------------------------------------------
SEKKI_NAMES = [
    ("春分", "しゅんぶん", 0), ("清明", "せいめい", 15), ("穀雨", "こくう", 30),
    ("立夏", "りっか", 45), ("小満", "しょうまん", 60), ("芒種", "ぼうしゅ", 75),
    ("夏至", "げし", 90), ("小暑", "しょうしょ", 105), ("大暑", "たいしょ", 120),
    ("立秋", "りっしゅう", 135), ("処暑", "しょしょ", 150), ("白露", "はくろ", 165),
    ("秋分", "しゅうぶん", 180), ("寒露", "かんろ", 195), ("霜降", "そうこう", 210),
    ("立冬", "りっとう", 225), ("小雪", "しょうせつ", 240), ("大雪", "たいせつ", 255),
    ("冬至", "とうじ", 270), ("小寒", "しょうかん", 285), ("大寒", "だいかん", 300),
    ("立春", "りっしゅん", 315), ("雨水", "うすい", 330), ("啓蟄", "けいちつ", 345),
]

# 七十二候（各節気を初候・次候・末候の3つ、5度刻みに分割。略本暦(現行版)準拠の名称）
KOU_NAMES_72 = [
    # 春分から順に、5度刻みで72個
    "雀始巣", "桜始開", "雷乃発声",                # 春分
    "玄鳥至", "鴻雁北", "虹始見",                  # 清明
    "葭始生", "霜止出苗", "牡丹華",                # 穀雨
    "蛙始鳴", "蚯蚓出", "竹笋生",                  # 立夏
    "蚕起食桑", "紅花栄", "麦秋至",                # 小満
    "螳螂生", "腐草為蛍", "梅子黄",                # 芒種
    "乃東枯", "菖蒲華", "半夏生",                  # 夏至
    "温風至", "蓮始開", "鷹乃学習",                # 小暑
    "桐始結花", "土潤溽暑", "大雨時行",            # 大暑
    "涼風至", "寒蝉鳴", "蒙霧升降",                # 立秋
    "綿柎開", "天地始粛", "禾乃登",                # 処暑
    "草露白", "鶺鴒鳴", "玄鳥去",                  # 白露
    "雷乃収声", "蟄虫坏戸", "水始涸",              # 秋分
    "鴻雁来", "菊花開", "蟋蟀在戸",                # 寒露
    "霜始降", "霎時施", "楓蔦黄",                  # 霜降
    "山茶始開", "地始凍", "金盞香",                # 立冬
    "虹蔵不見", "朔風払葉", "橘始黄",              # 小雪
    "閉塞成冬", "熊蟄穴", "鱖魚群",                # 大雪
    "乃東生", "麋角解", "雪下出麦",                # 冬至
    "芹乃栄", "水泉動", "雉始雊",                  # 小寒
    "款冬華", "水沢腹堅", "鶏始乳",                # 大寒
    "東風解凍", "黄鶯睍睆", "魚上氷",              # 立春
    "土脉潤起", "霞始靆", "草木萌動",              # 雨水
    "蟄虫啓戸", "桃始笑", "菜虫化蝶",              # 啓蟄
]

# 中気（旧暦の月番号を決めるための12節気。黄経を30度刻み。won=対応する旧暦月）
# 冬至(270度)を含む月が11月、雨水(330度)を含む月が1月...という対応
CHUUKI_TO_MONTH = {
    270: 11, 300: 12, 330: 1, 0: 2, 30: 3, 60: 4,
    90: 5, 120: 6, 150: 7, 180: 8, 210: 9, 240: 10,
}


def sun_ecliptic_longitude(dt_utc):
    """指定UTC日時における太陽の視黄経(度, 0-360, of-date)を返す"""
    obs = ephem.Observer()
    obs.date = dt_utc
    sun = ephem.Sun(obs)
    eq = ephem.Equatorial(sun.ra, sun.dec, epoch=obs.date)
    ecl = ephem.Ecliptic(eq)
    return math.degrees(float(ecl.lon)) % 360


def find_longitude_crossing(target_lon, start_dt_utc, search_days=40):
    """start_dt_utc から前方に探索し、太陽黄経が target_lon を通過する瞬間(UTC)を二分探索で求める"""
    def diff(dt):
        lon = sun_ecliptic_longitude(dt)
        d = (lon - target_lon + 180) % 360 - 180
        return d

    lo = start_dt_utc
    hi = start_dt_utc + timedelta(days=search_days)
    d_lo = diff(lo)
    # 符号が変わる区間を1日刻みで探す
    step = timedelta(days=1)
    t = lo
    prev_d = d_lo
    found = None
    while t < hi:
        t2 = t + step
        d2 = diff(t2)
        if prev_d < 0 <= d2 or (prev_d <= 0 and d2 > 0):
            found = (t, t2)
            break
        t, prev_d = t2, d2
    if not found:
        raise ValueError("crossing not found in range")
    a, b = found
    for _ in range(50):
        mid = a + (b - a) / 2
        if diff(mid) < 0:
            a = mid
        else:
            b = mid
    return a + (b - a) / 2


def get_sekki_and_kou(target_date_jst):
    """
    target_date_jst (date) の二十四節気・七十二候を判定。
    判定基準は「その日の終わり(23:59:59 JST)」時点の太陽黄経。
    こうすることで、暦要項の慣例(節気切替が起きた"その日"から新しい節気とする)
    と一致させる。例:白露が9/7 23:41に始まる場合、9/7はすでに白露として扱う。
    """
    dt_utc = datetime(target_date_jst.year, target_date_jst.month, target_date_jst.day,
                       23, 59, 59, tzinfo=JST).astimezone(timezone.utc)
    lon = sun_ecliptic_longitude(dt_utc)

    # 24節気: 15度刻みでどの区間か
    sekki_index = int(lon // 15)
    sekki_lon = sekki_index * 15
    sekki_name, sekki_yomi, _ = next(s for s in SEKKI_NAMES if s[2] == sekki_lon)

    # 72候: 5度刻みでどの区間か（0度=春分始まりのインデックス、リストは春分始まり）
    kou_index_from_shunbun = int(lon // 5)  # 0..71
    kou_name = KOU_NAMES_72[kou_index_from_shunbun]

    # 節気内での何番目の候か(初候/次候/末候)
    sub = (lon - sekki_lon) // 5
    sub_label = ["初候", "次候", "末候"][int(sub)]

    return {
        "solar_longitude": round(lon, 4),
        "sekki_name": sekki_name,
        "sekki_yomi": sekki_yomi,
        "kou_name": kou_name,
        "kou_label": sub_label,
    }


# 旧暦の日にちごとの伝統的な月の呼び名(主要なもの。それ以外は満ち欠けの方向で補う)
MOON_PHASE_NAMES = {
    1: "新月", 2: "二日月", 3: "三日月",
    7: "上弦の月", 8: "上弦の月",
    10: "十日夜の月", 13: "十三夜月", 14: "小望月",
    15: "満月", 16: "十六夜", 17: "立待月", 18: "居待月",
    19: "寝待月", 20: "更待月",
    22: "下弦の月", 23: "下弦の月", 26: "二十六夜月",
    30: "晦日月",
}


def moon_phase_name(kyureki_day: int) -> str:
    """旧暦の日にち(1-30)から、伝統的な月の呼び名を返す"""
    if kyureki_day in MOON_PHASE_NAMES:
        return MOON_PHASE_NAMES[kyureki_day]
    if kyureki_day < 15:
        return "満ちていく月"
    return "欠けていく月"


TOKYO_LAT = "35.6895"
TOKYO_LON = "139.6917"

DIRECTIONS_8 = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"]


def _azimuth_to_direction(az_deg: float) -> str:
    idx = int(((az_deg + 22.5) % 360) // 45)
    return DIRECTIONS_8[idx]


def moon_position_at(target_date_jst, hour=20, minute=0):
    """指定した時刻(デフォルト20時 JST)における月の高度・方位を返す"""
    obs = ephem.Observer()
    obs.lat = TOKYO_LAT
    obs.lon = TOKYO_LON
    dt_utc = datetime(target_date_jst.year, target_date_jst.month, target_date_jst.day,
                       hour, minute, 0, tzinfo=JST).astimezone(timezone.utc)
    obs.date = dt_utc
    moon = ephem.Moon(obs)
    altitude_deg = math.degrees(float(moon.alt))
    azimuth_deg = math.degrees(float(moon.az))
    return altitude_deg, azimuth_deg


def moon_position_description(target_date_jst) -> str:
    """
    その日の夜(20時 JST基準)に月がどの方角にどれくらいの高さで見えるかを
    自然な日本語の一文で返す。地平線の下にある場合は、月の出/月の入りの
    時刻を案内する文にする。
    """
    altitude_deg, azimuth_deg = moon_position_at(target_date_jst, hour=20)
    direction = _azimuth_to_direction(azimuth_deg)

    if altitude_deg > 50:
        height_desc = "空高く"
    elif altitude_deg > 20:
        height_desc = "ほどよい高さに"
    elif altitude_deg > 0:
        height_desc = "低い位置に"
    else:
        height_desc = None

    if height_desc:
        return f"今夜20時頃には、{direction}の空の{height_desc}月が見えています。"

    # 地平線の下にある場合は、月の出または月の入りの時刻を調べて案内する
    obs = ephem.Observer()
    obs.lat = TOKYO_LAT
    obs.lon = TOKYO_LON
    dt_utc = datetime(target_date_jst.year, target_date_jst.month, target_date_jst.day,
                       0, 0, 0, tzinfo=JST).astimezone(timezone.utc)
    obs.date = dt_utc
    moon = ephem.Moon()
    try:
        next_rise = obs.next_rising(moon).datetime().replace(tzinfo=timezone.utc).astimezone(JST)
        next_set = obs.next_setting(moon).datetime().replace(tzinfo=timezone.utc).astimezone(JST)
        if next_rise.date() == target_date_jst and (next_set.date() != target_date_jst or next_rise < next_set):
            return f"本日は{next_rise.strftime('%H時%M分')}頃に月の出を迎え、これから夜空に昇ってきます。"
        elif next_set.date() == target_date_jst:
            return f"本日は{next_set.strftime('%H時%M分')}頃に月の入りを迎え、夜更けには見えなくなります。"
        else:
            return "本日は日中に月が昇るため、夜にはすでに沈んでしまっている時間帯です。"
    except Exception:
        return "本日は月の出入りの時間帯により、夜空では見えにくくなっています。"


def moon_age(target_date_jst):
    """月齢(前回新月からの経過日数)を返す。国立天文台の慣例に合わせ正午(12:00 JST)基準で算出"""
    dt_utc = datetime(target_date_jst.year, target_date_jst.month, target_date_jst.day,
                       12, 0, 0, tzinfo=JST).astimezone(timezone.utc)
    prev_new = ephem.previous_new_moon(dt_utc).datetime().replace(tzinfo=timezone.utc)
    age = (dt_utc - prev_new).total_seconds() / 86400
    return round(age, 2)


def compute_kyuureki(target_date_jst):
    """
    旧暦(太陰太陽暦)を計算する。
    アルゴリズム:
      1. 対象日を含む朔(新月)の日を求め、そこから遡って各月の開始日(朔)を列挙
      2. 各月に含まれる中気を調べ、月番号を決定
      3. 中気を含まない月があれば閏月とする
    """
    # 「その日の終わり(23:59:59 JST)」を基準にすることで、対象日当日に新月が
    # 起きた場合でもその日を新しい月の1日目として正しく判定できるようにする
    end_of_day_jst = datetime(target_date_jst.year, target_date_jst.month, target_date_jst.day,
                               23, 59, 59, tzinfo=JST).astimezone(timezone.utc)

    # 対象日が属する朔(月の始まり)を求める
    this_new_moon = ephem.previous_new_moon(end_of_day_jst)
    # JSTでの「日」に変換(朔があった瞬間を含む日がその月の1日)
    def new_moon_to_jst_date(nm):
        d = nm.datetime().replace(tzinfo=timezone.utc).astimezone(JST)
        return d.date()

    # 前後十分な範囲の朔を列挙(冬至を最低1つ含むまで遡る)
    new_moons = [this_new_moon]
    nm = this_new_moon
    for _ in range(15):
        nm = ephem.previous_new_moon(nm.datetime() - timedelta(hours=1))
        new_moons.insert(0, nm)
    # 対象日を含む月の「終わり」を確定するため、次の朔も追加
    next_nm = ephem.next_new_moon(this_new_moon.datetime() + timedelta(hours=1))
    new_moons.append(next_nm)

    # 各月(朔から次の朔の前日まで)に含まれる中気を調べる
    months = []  # [(start_date_jst, end_date_jst, chuuki_lon or None)]
    for i in range(len(new_moons) - 1):
        start = new_moon_to_jst_date(new_moons[i])
        end = new_moon_to_jst_date(new_moons[i + 1])
        start_lon = sun_ecliptic_longitude(datetime(start.year, start.month, start.day, tzinfo=JST).astimezone(timezone.utc))
        end_lon = sun_ecliptic_longitude(datetime(end.year, end.month, end.day, tzinfo=JST).astimezone(timezone.utc))
        chuuki_lon = None
        for chuuki_deg in CHUUKI_TO_MONTH:
            lo, hi = start_lon, end_lon
            if lo > hi:  # 360度をまたぐ場合
                hi += 360
                cd = chuuki_deg if chuuki_deg >= lo else chuuki_deg + 360
            else:
                cd = chuuki_deg
            if lo <= cd < hi:
                chuuki_lon = chuuki_deg
                break
        months.append([start, end, chuuki_lon])

    # 月番号を割り当て(中気を含む月から番号を確定し、含まない月は閏月とする)
    labeled = []
    running_month = None
    for start, end, chuuki_lon in months:
        if chuuki_lon is not None:
            running_month = CHUUKI_TO_MONTH[chuuki_lon]
            labeled.append([start, end, running_month, False])
        else:
            if running_month is None:
                labeled.append([start, end, None, False])
            else:
                labeled.append([start, end, running_month, True])  # 閏月(前の月と同番号)

    # target_date_jst が含まれる月を特定
    for start, end, month_no, is_leap in labeled:
        if start <= target_date_jst < end:
            day_no = (target_date_jst - start).days + 1
            return {
                "kyureki_month": month_no,
                "kyureki_day": day_no,
                "is_leap_month": is_leap,
                "month_start_date": start,
            }
    raise ValueError("could not determine kyuureki for date")


if __name__ == "__main__":
    test_dates = [
        datetime(2026, 9, 18).date(),
        datetime(2026, 1, 1).date(),
        datetime(2025, 1, 29).date(),
        datetime(2023, 3, 22).date(),
    ]
    for d in test_dates:
        sk = get_sekki_and_kou(d)
        ma = moon_age(d)
        ky = compute_kyuureki(d)
        print(f"--- {d} ---")
        print(f"  太陽黄経: {sk['solar_longitude']}度")
        print(f"  二十四節気: {sk['sekki_name']}({sk['sekki_yomi']})")
        print(f"  七十二候: {sk['kou_name']}（{sk['kou_label']}）")
        print(f"  月齢: {ma}")
        print(f"  旧暦: {'閏' if ky['is_leap_month'] else ''}{ky['kyureki_month']}月{ky['kyureki_day']}日 (この月の朔:{ky['month_start_date']})")
