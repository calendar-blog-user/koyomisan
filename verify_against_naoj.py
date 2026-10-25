"""
計算結果を、国立天文台(NAOJ)暦要項などの公表値と照合する検証スクリプト。
    python verify_against_naoj.py
計算ロジックを変更したときは、必ずこれを実行して「NG」が出ないことを確認する。

照合の基準:
  - 国立天文台 暦要項 令和8年(2026)・令和9年(2027): 東京の日出入、国民の祝日、雑節
  - 国立天文台 暦計算室「今日のこよみ」(2026-10-09 東京)、およびユーザー提示の岡山の値
  - 国立天文台 暦要項の朔弦望(2026・2027年)、ほしぞら情報(2026年の流星群の極大)、月食一覧(2030年まで)
  - 第三者サイトの公表値(一粒万倍日の年間日数、東京2026年9月の月の出入り、2026・2027年の天赦日・不成就日・寅の日・巳の日)
"""
import sys
from datetime import date, timedelta

import calendar_extras as ce
from sunmoon import sun_moon_times, CITY_BY_ID

NG = 0
TOKYO_NAOJ = (35 + 39 / 60, 139 + 44 / 60)  # 暦要項の「東京」(北緯35°39′ 東経139°44′)


def report(label, ok, detail=""):
    global NG
    print(f"{'OK' if ok else 'NG'}  {label}" + (f"  {detail}" if detail and not ok else ""))
    NG += (not ok)


def tomin(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


# ---- 東京の日出入 (暦要項 (月, 日): (日出, 日入)) ----
SUN_2026 = """1 1 6:51 16:38|1 11 6:51 16:47|1 21 6:48 16:57|1 31 6:42 17:07|2 10 6:33 17:17|2 20 6:23 17:27|3 2 6:10 17:37|3 12 5:57 17:46|3 22 5:42 17:54|4 1 5:28 18:02|4 11 5:14 18:11|4 21 5:01 18:19|5 1 4:50 18:27|5 11 4:40 18:36|5 21 4:32 18:44|5 31 4:27 18:51|6 10 4:25 18:56|6 20 4:25 19:00|6 30 4:28 19:01|7 10 4:33 18:59|7 20 4:40 18:55|7 30 4:47 18:47|8 9 4:55 18:38|8 19 5:03 18:26|8 29 5:10 18:13|9 8 5:18 17:59|9 18 5:25 17:45|9 28 5:33 17:30|10 8 5:41 17:16|10 18 5:50 17:02|10 28 5:59 16:51|11 7 6:08 16:41|11 17 6:18 16:33|11 27 6:28 16:29|12 7 6:37 16:28|12 17 6:44 16:30|12 27 6:49 16:35"""
SUN_2027 = """1 1 6:50 16:38|1 11 6:51 16:47|1 21 6:48 16:57|1 31 6:42 17:07|2 10 6:34 17:17|2 20 6:23 17:27|3 2 6:11 17:37|3 12 5:57 17:45|3 22 5:43 17:54|4 1 5:29 18:02|4 11 5:15 18:10|4 21 5:02 18:19|5 1 4:50 18:27|5 11 4:40 18:35|5 21 4:32 18:43|5 31 4:27 18:50|6 10 4:25 18:56|6 20 4:25 19:00|6 30 4:28 19:01|7 10 4:33 18:59|7 20 4:40 18:55|7 30 4:47 18:48|8 9 4:55 18:38|8 19 5:02 18:27|8 29 5:10 18:14|9 8 5:18 18:00|9 18 5:25 17:45|9 28 5:33 17:30|10 8 5:41 17:16|10 18 5:49 17:03|10 28 5:58 16:51|11 7 6:08 16:41|11 17 6:18 16:33|11 27 6:28 16:29|12 7 6:37 16:28|12 17 6:44 16:30|12 27 6:49 16:35"""


def check_sun(year, table):
    exact = within1 = n = 0
    for line in table.split("|"):
        mo, dy, rise, sset = line.split()
        r = sun_moon_times(date(year, int(mo), int(dy)), *TOKYO_NAOJ)
        for got, want in ((r["sunrise"], rise), (r["sunset"], sset)):
            n += 1
            exact += (got == want)
            within1 += (abs(tomin(got) - tomin(want)) <= 1)
    # 全値が±1分以内、かつ完全一致が9割以上
    report(f"東京の日出入 {year}年 暦要項 {n}値", within1 == n and exact / n >= 0.9,
           f"完全一致{exact}/{n}, ±1分以内{within1}/{n}")
    print(f"      (完全一致 {exact}/{n}, ±1分以内 {within1}/{n})")


check_sun(2026, SUN_2026)
check_sun(2027, SUN_2027)

# ---- 今日のこよみ (2026-10-09) ----
for label, cid, want in (
    ("NAOJ今日のこよみ 東京", "tokyo", ("5:42", "11:28", "17:14", "4:00", "10:12", "16:15")),
    ("岡山(ユーザー提示のNAOJ値)", "okayama", ("6:05", "11:52", "17:38", "4:24", "10:36", "16:39")),
):
    c = CITY_BY_ID[cid]
    r = sun_moon_times(date(2026, 10, 9), c["lat"], c["lon"])
    got = (r["sunrise"], r["solar_noon"], r["sunset"], r["moonrise"], r["moon_transit"], r["moonset"])
    report(f"{label} 日の出・南中・日の入・月の出・月南中・月の入", got == want, f"{got} != {want}")

# ---- 東京2026年9月1〜8日の月の出入り (第三者サイト。日の出入りは暦要項と整合) ----
MOON_SEP = {1: ("20:03", "9:07"), 2: ("20:38", "10:16"), 3: ("21:21", "11:27"), 4: ("22:13", "12:38"),
            5: ("23:14", "13:45"), 6: (None, "14:45"), 7: ("0:24", "15:35"), 8: ("1:37", "16:16")}
tk = CITY_BY_ID["tokyo"]
ok = all((sun_moon_times(date(2026, 9, d), tk["lat"], tk["lon"])["moonrise"],
          sun_moon_times(date(2026, 9, d), tk["lat"], tk["lon"])["moonset"]) == w for d, w in MOON_SEP.items())
report("東京2026年9月1〜8日の月の出・月の入り(16値、月の出なしの日を含む)", ok)

# ---- 国民の祝日 ----
HOL_2026 = {"01/01": "元日", "01/12": "成人の日", "02/11": "建国記念の日", "02/23": "天皇誕生日", "03/20": "春分の日",
            "04/29": "昭和の日", "05/03": "憲法記念日", "05/04": "みどりの日", "05/05": "こどもの日", "05/06": "振替休日",
            "07/20": "海の日", "08/11": "山の日", "09/21": "敬老の日", "09/22": "国民の休日", "09/23": "秋分の日",
            "10/12": "スポーツの日", "11/03": "文化の日", "11/23": "勤労感謝の日"}
HOL_2027 = {"01/01": "元日", "01/11": "成人の日", "02/11": "建国記念の日", "02/23": "天皇誕生日", "03/21": "春分の日",
            "03/22": "振替休日", "04/29": "昭和の日", "05/03": "憲法記念日", "05/04": "みどりの日", "05/05": "こどもの日",
            "07/19": "海の日", "08/11": "山の日", "09/20": "敬老の日", "09/23": "秋分の日", "10/11": "スポーツの日",
            "11/03": "文化の日", "11/23": "勤労感謝の日"}
for y, want in ((2026, HOL_2026), (2027, HOL_2027)):
    got = {d.strftime("%m/%d"): v[0] for d, v in ce.holidays_in_year(y).items()}
    report(f"国民の祝日 {y}年 暦要項 {len(want)}日(振替休日・国民の休日を含む)", got == want,
           f"差分: 多い={set(got.items()) - set(want.items())} 不足={set(want.items()) - set(got.items())}")

# ---- 雑節 (暦要項) ----
def md(ds): return [d.strftime("%m/%d") for d in sorted(ds)]
def zdates(y, name):
    return [d for d, ns in ce.zassetsu_in_year(y).items() if any(n.split("（")[0] == name for n in ns)]

ZASSETSU_WANT = {
    2026: {"彼岸入り": ["03/17", "09/20"], "土用入り": ["01/17", "04/17", "07/20", "10/20"], "八十八夜": ["05/02"],
           "入梅": ["06/11"], "半夏生": ["07/02"], "二百十日": ["09/01"]},
    2027: {"彼岸入り": ["03/18", "09/20"], "土用入り": ["01/17", "04/17", "07/20", "10/21"], "八十八夜": ["05/02"],
           "入梅": ["06/11"], "半夏生": ["07/02"], "二百十日": ["09/01"]},
}
SETSUBUN_WANT = {2026: "02/03", 2027: "02/03"}
for y, table in ZASSETSU_WANT.items():
    for name, want in table.items():
        report(f"雑節 {y}年 {name}", md(zdates(y, name)) == want, f"{md(zdates(y, name))} != {want}")
    setsubun = ce.risshun(y) - timedelta(days=1)
    report(f"雑節 {y}年 節分", setsubun.strftime("%m/%d") == SETSUBUN_WANT[y])

# ---- 一粒万倍日 (第三者サイトの年間日数) ----
def count_ichiryu(y):
    d, n = date(y, 1, 1), 0
    while d.year == y:
        n += ce.is_ichiryu_manbai(d)
        d += timedelta(days=1)
    return n

for y, want in ((2026, 64), (2027, 60), (2028, 62), (2029, 57), (2030, 62), (2031, 59)):
    report(f"一粒万倍日の年間日数 {y}年 = {want}日", count_ichiryu(y) == want, f"{count_ichiryu(y)}")

# ---- 社日 (公表値 2016〜2026 春、2016〜2023・2025 秋) ----
SPRING = {2016: (3, 17), 2017: (3, 22), 2018: (3, 17), 2019: (3, 22), 2020: (3, 16), 2021: (3, 21),
          2022: (3, 16), 2023: (3, 21), 2024: (3, 15), 2025: (3, 20), 2026: (3, 15)}
AUTUMN = {2016: (9, 23), 2017: (9, 18), 2018: (9, 23), 2019: (9, 18), 2020: (9, 22), 2021: (9, 27),
          2022: (9, 22), 2023: (9, 27), 2025: (9, 26)}
ok = all((lambda d: (d.month, d.day) == w)(ce._nearest_tsuchinoe(ce.shunbun(y))) for y, w in SPRING.items()) and \
     all((lambda d: (d.month, d.day) == w)(ce._nearest_tsuchinoe(ce.shubun(y))) for y, w in AUTUMN.items())
report("社日 公表値20件(2016〜2026)", ok)

# ---- 干支・六曜 ----
from koyomi_engine import compute_kyuureki
report("日の干支 2000-01-01=戊午", ce.kanshi_name(date(2000, 1, 1)) == "戊午")
report("日の干支 2026-09-26=癸卯(第三者サイト)", ce.kanshi_name(date(2026, 9, 26)) == "癸卯")

# 日の干支の説明(その日の意味: 五行の性質・関係・暦注)
_YOMI = {"甲子": "きのえね", "乙丑": "きのとうし", "丙寅": "ひのえとら", "丁卯": "ひのとう", "戊辰": "つちのえたつ",
         "己巳": "つちのとみ", "庚午": "かのえうま", "辛未": "かのとひつじ", "壬申": "みずのえさる",
         "癸酉": "みずのととり", "甲戌": "きのえいぬ", "乙亥": "きのとい", "癸亥": "みずのとい", "辛酉": "かのととり"}
_ki = {}
for _k in range(60):
    _x = ce.kanshi_info(date(2026, 1, 1) + timedelta(days=_k))
    _ki[_x["name"]] = _x
report("日の干支の説明: 60日で60通りすべてに、読みと説明と補足がある", len(_ki) == 60 and all(v["yomi"] and v["desc"] and v["note"] for v in _ki.values()))
report("日の干支の読み: 代表14通りが、標準の読みと一致する", all(_ki[k]["yomi"] == v for k, v in _YOMI.items()))
_k = _ki["己巳"]
report("日の干支の意味: 己巳(土と火)は、詳しい説明に「火が土を助ける相生」、短い説明に「周りの支えを受けやすい」が出る",
       _k["detail"].startswith("土（安定・育成）と火（活気・情熱）の性質を持つ日です。") and "火が土を助ける相生" in _k["detail"]
       and _k["desc"].startswith("周りの支えを受けやすい日です。") and "相生" not in _k["desc"] and _k["relation"] == "支生干")
_k = _ki["壬寅"]
report("日の干支の意味: 壬寅(水と木)は、「水が木を生み出す相生」で、農作業に向く日になる(詳しい説明)",
       "水（知恵・流れ）と木（芽吹き・成長）の性質を持つ日です。" in _k["detail"] and "水が木を生み出す相生" in _k["detail"] and "農作業に向く日" in _k["detail"])
_k = _ki["甲子"]
report("日の干支の短い説明: 甲子は、「支えを受けやすい」「農作業や勉強、情報集め」「甲子待」の3文だけになる",
       _k["desc"] == "周りの支えを受けやすい日です。農作業や勉強、情報集めに向く日といわれます。大黒天をまつる「甲子待（きのえねまち）」の日とされ、福を願う習わしがあります。")
_SH = {("木", "火"), ("火", "土"), ("土", "金"), ("金", "水"), ("水", "木")}      # 相生(前が後ろを生む)
_SK = {("木", "土"), ("土", "水"), ("水", "火"), ("火", "金"), ("金", "木")}      # 相剋(前が後ろを抑える)
def _rel(a, b):
    return "比和" if a == b else "干生支" if (a, b) in _SH else "支生干" if (b, a) in _SH else "干剋支" if (a, b) in _SK else "支剋干"
report("日の干支の関係(相生・相剋・比和): 60通りすべて、独立に求めた関係と一致する",
       all(v["relation"] == _rel(v["stem_gogyo"], v["branch_gogyo"]) for v in _ki.values())
       and {v["relation"] for v in _ki.values()} == {"比和", "干生支", "支生干", "干剋支", "支剋干"})
_cnt = {}
for _v in _ki.values():
    for _r in _v["rekichu"]:
        _cnt[_r] = _cnt.get(_r, 0) + 1
report("日の干支の暦注: 大犯土7日・小犯土7日・間日1日・十方暮10日・天一天上16日・甲子待1日・庚申待1日",
       _cnt == {"大犯土": 7, "小犯土": 7, "犯土の間日": 1, "十方暮": 10, "天一天上": 16, "甲子待": 1, "庚申待": 1}, str(_cnt))
report("日の干支の暦注: 範囲の端(庚午・丙子=大犯土、戊寅=小犯土、甲申=小犯土と十方暮、癸巳=十方暮と天一天上、戊申=天一天上、丁丑=間日)",
       "大犯土" in _ki["庚午"]["rekichu"] and "大犯土" in _ki["丙子"]["rekichu"] and "小犯土" in _ki["戊寅"]["rekichu"]
       and set(_ki["甲申"]["rekichu"]) == {"小犯土", "十方暮"} and set(_ki["癸巳"]["rekichu"]) == {"十方暮", "天一天上"}
       and _ki["戊申"]["rekichu"] == ["天一天上"] and _ki["丁丑"]["rekichu"] == ["犯土の間日"] and _ki["己巳"]["rekichu"] == [])
report("日の干支の暦注: 土いじりを慎む犯土の日は、農作業などを勧める文を出さず、暦注の文を出す(短い・詳しい説明とも)",
       all(("向く日といわれます" not in v[k]) and ("土いじりは慎む" in v[k]) for v in _ki.values() if set(v["rekichu"]) & {"大犯土", "小犯土"} for k in ("desc", "detail"))
       and all("向く日といわれます" in v["desc"] or "向くといわれます" in v["desc"] for v in _ki.values() if not (set(v["rekichu"]) & {"大犯土", "小犯土"})))
k = compute_kyuureki(date(2026, 9, 26))
report("六曜 2026-09-26(旧8/16)=大安(第三者サイト)", ce.rokuyo_name(k["kyureki_month"], k["kyureki_day"]) == "大安")
k = compute_kyuureki(date(2025, 1, 29))
report("六曜 旧暦1月1日=先勝", ce.rokuyo_name(k["kyureki_month"], k["kyureki_day"]) == "先勝")

# =====================================================================
# 追加: 朔弦望・流星群・日食月食・選日・昼の長さ
# =====================================================================
from collections import Counter
import astro_events as ae
from sunmoon import day_length_seconds

# ---- 朔弦望 (暦要項 2026・2027。PDFから抽出した行。数字が詰まるため、数字の並びで照合する) ----
RAW_2026 = """望 13 19 3|下弦 1 11 0 48|朔 1 19 4 52|上弦 1 26 13 47|望 22 79|下弦 29 21 43|朔 2 17 21 1|上弦 2 24 21 28|望 33 20 38|下弦 3 11 18 39|朔 3 19 10 23|上弦 3 26 4 18|望 42 11 12|下弦 4 10 13 52|朔 4 17 20 52|上弦 4 24 11 32|望 52 2 23|下弦 5 10 6 10|朔 5 17 51|上弦 5 23 20 11|望 5 31 17 45|下弦 68 19 1|朔 6 15 11 54|上弦 6 22 6 55|望 6 30 8 57|下弦 78 4 29|朔 7 14 18 44|上弦 7 21 20 6|望 7 29 23 36|下弦 86 11 21|朔 8 13 2 37|上弦 8 20 11 46|望 8 28 13 19|下弦 94 16 51|朔 9 11 12 27|上弦 9 19 5 44|望 9 27 1 49|下弦 10 3 22 25|朔 10 11 0 50|上弦 10 19 1 13|望 10 26 13 12|下弦 11 2 5 28|朔 11 9 16 2|上弦 11 17 20 48|望 11 24 23 54|下弦 12 1 15 9|朔 12 9 9 52|上弦 12 17 14 43|望 12 24 10 28|下弦 12 31 3 59"""
RAW_2027 = """朔 1 8 5 24|上弦 1 16 5 35|望 1 22 21 17|下弦 1 29 19 55|朔 2 7 0 56|上弦 2 14 16 58|望 2 21 8 24|下弦 2 28 14 17|朔 3 8 18 29|上弦 3 16 1 25|望 3 22 19 44|下弦 3 30 9 54|朔 4 7 8 51|上弦 4 14 7 57|望 4 21 7 27|下弦 4 29 5 18|朔 5 6 19 59|上弦 5 13 13 44|望 5 20 19 59|下弦 5 28 22 58|朔 6 5 4 40|上弦 6 11 19 56|望 6 19 9 44|下弦 6 27 13 54|朔 7 4 12 2|上弦 7 11 3 39|望 7 19 0 45|下弦 7 27 1 55|朔 8 2 19 5|上弦 8 9 13 54|望 8 17 16 29|下弦 8 25 11 27|朔 9 1 2 41|上弦 9 8 3 31|望 9 16 8 4|下弦 9 23 19 20|朔 9 30 11 36|上弦 10 7 20 47|望 10 15 22 47|下弦 10 23 2 29|朔 10 29 22 37|上弦 11 6 17 0|望 11 14 12 26|下弦 11 21 9 48|朔 11 28 12 24|上弦 12 6 14 22|望 12 14 1 9|下弦 12 20 18 11|朔 12 28 5 12"""
total = ok = within1 = 0
for year, raw in ((2026, RAW_2026), (2027, RAW_2027)):
    pdf = Counter((l.split()[0], "".join(l.split()[1:])) for l in raw.split("|"))
    mine = Counter((k, f"{dt.month}{dt.day}{dt.hour}{dt.minute}") for k, dt in ae.phase_events_year(year))
    total += sum(pdf.values()); ok += sum((pdf & mine).values())
report(f"朔弦望(新月・上弦・満月・下弦) 2026・2027年 暦要項 {total}件 (完全一致{ok}件、残りも1分差)", ok >= total - 2,
       f"完全一致{ok}/{total}")
print(f"      (完全一致 {ok}/{total})")

# ---- 流星群の極大 (国立天文台 ほしぞら情報 2026年。「時」まで一致するか) ----
NAOJ_METEOR_2026 = {"しぶんぎ座流星群": (1, 4, 6), "4月こと座流星群": (4, 23, 5), "ペルセウス座流星群": (8, 13, 11),
                    "ふたご座流星群": (12, 14, 23)}
OTHER_METEOR_2026 = {"オリオン座流星群": (10, 22, 3), "しし座流星群": (11, 18, 9), "10月りゅう座流星群": (10, 9, 10),
                     "みずがめ座η流星群": (5, 6, 18)}   # 国立天文台の予報を引用した情報(Webニュース等)による
for label, table in (("国立天文台ほしぞら情報で直接確認した4件", NAOJ_METEOR_2026), ("国立天文台の予報を引用した情報の4件", OTHER_METEOR_2026)):
    good = all((lambda pk: (pk.month, pk.day, pk.hour) == w)(ae.meteor_peak_rounded(2026, n)) for n, w in table.items())
    report(f"流星群の極大(2026年): {label}", good, str({n: ae.meteor_peak_rounded(2026, n).strftime('%m/%d %H時') for n in table}))

# 月明かり(見頃の3時)が、国立天文台の記述と一致するか(2026年)
MOON_NAOJ = {"しぶんぎ座流星群": "影響あり(満月で邪魔になる)", "4月こと座流星群": "影響なし", "ペルセウス座流星群": "影響なし(新月)",
             "オリオン座流星群": "影響なし(未明に月が沈む)", "しし座流星群": "影響なし", "ふたご座流星群": "影響なし(21時までに月が沈む)"}
for name, expect in MOON_NAOJ.items():
    txt = ae.moon_condition_text(ae.meteor_peak_rounded(2026, name))
    bad = "見えにくくなります" in txt
    report(f"月明かりの判定(2026年) {name}: 国立天文台の記述='{expect}'", bad == expect.startswith("影響あり"), txt)

# ---- 月食・日食の一覧 (国立天文台 月食一覧・暦要項) ----
want_ecl = [(2026, 3, 3, "皆既月食"), (2028, 7, 7, "部分月食"), (2029, 1, 1, "皆既月食"), (2029, 12, 21, "皆既月食"),
            (2030, 6, 1, "金環日食"), (2030, 6, 16, "部分月食")]
report("日本で見られる日食・月食の一覧(国立天文台 月食一覧2026〜2030年・日食は2030/6/1)",
       [(e["date"].year, e["date"].month, e["date"].day, e["kind"]) for e in ae.ECLIPSES] == want_ecl)
report("2026-03-03 皆既月食の日付が、望(満月)の日と一致(暦要項 3/3 20:38)",
       any(p["kind"] == "望" for p in ae.phases_on(date(2026, 3, 3))))

# ---- 選日 (第三者サイトの公表値。2026・2027年) ----
def days_of(year, pred):
    d, out = date(year, 1, 1), []
    while d.year == year:
        if pred(d): out.append((d.month, d.day))
        d += timedelta(days=1)
    return out
report("天赦日 2026年(6日: 3/5, 5/4, 5/20, 7/19, 10/1, 12/16)",
       days_of(2026, ce.is_tenshanichi) == [(3, 5), (5, 4), (5, 20), (7, 19), (10, 1), (12, 16)])
report("天赦日 2027年に 9/26 を含む(同日は不成就日とも重なる)", (9, 26) in days_of(2027, ce.is_tenshanichi))
def fuj(d):
    k = compute_kyuureki(d); return ce.is_fujojubi(k["kyureki_month"], k["kyureki_day"])
fj = days_of(2026, fuj)
report("不成就日 2026年7月 = {5, 13, 19, 27}", sorted(m_d[1] for m_d in fj if m_d[0] == 7) == [5, 13, 19, 27])
listed = [(1, 9), (2, 19), (3, 7), (5, 3), (5, 20), (5, 28), (6, 19), (7, 5), (7, 13), (7, 19), (7, 27), (10, 6), (10, 11), (10, 19)]
report("不成就日 2026年 公表されている14日をすべて含む", all(x in fj for x in listed), str([x for x in listed if x not in fj]))
tora = days_of(2026, lambda d: ce.day_branch(d) == "寅"); mi = days_of(2026, lambda d: ce.day_branch(d) == "巳")
report("寅の日 2026年(1/4, 1/28, 3/5, 5/4, 5/28, 7/3, 7/15, 7/27, 10/7, 10/19)",
       all(x in tora for x in [(1, 4), (1, 28), (3, 5), (5, 4), (5, 28), (7, 3), (7, 15), (7, 27), (10, 7), (10, 19)]))
report("巳の日 2026年(5/7, 5/19, 7/6, 7/18, 7/30, 10/10, 10/22)",
       all(x in mi for x in [(5, 7), (5, 19), (7, 6), (7, 18), (7, 30), (10, 10), (10, 22)]))
report("己巳の日 2026-10-22", ce.kanshi_name(date(2026, 10, 22)) == "己巳")

# ---- 昼の長さ (暦要項の東京の日出入から求めた昼の長さ) ----
rows = []
for year, table in ((2026, SUN_2026), (2027, SUN_2027)):
    for line in table.split("|"):
        mo, dy, rise, sset = line.split()
        rows.append((date(year, int(mo), int(dy)), tomin(sset) - tomin(rise)))
diffs = [round(day_length_seconds(d, *TOKYO_NAOJ) / 60) - L for d, L in rows]
report(f"昼の長さ(東京) 暦要項2026・2027年 {len(rows)}日: 全日±1分以内", all(abs(x) <= 1 for x in diffs), f"最大{max(abs(x) for x in diffs)}分")

# =====================================================================
# 追加: 通知のタイトル・本文(「今日は何の日だから通知しているか」が分かるか)
# =====================================================================
from render_koyomi import build_message, build_reasons, get_full_data, load_databases, render_text
import calendar_data as cd
_dbs = load_databases()
_fd_cache = {}
def _fd(d):
    """その日の構造化データ(1日1回だけ計算して使い回す。ここでは雑節・選日・一粒万倍日がONの状態の結果)"""
    if d not in _fd_cache:
        _fd_cache[d] = get_full_data(d, _dbs)
    return _fd_cache[d]

# 雑節・選日・一粒万倍日の通知設定(calendar_data.py)。従来のきっかけだけの検査では、いったんOFFにする
_ON = (cd.NOTIFY_ZASSETSU, cd.NOTIFY_ICHIRYU_MANBAI, dict(cd.NOTIFY_SENJITSU))
def _set_extra(on):
    cd.NOTIFY_ZASSETSU = on
    cd.NOTIFY_ICHIRYU_MANBAI = on
    cd.NOTIFY_SENJITSU = {k: on for k in _ON[2]}
def _restore_extra():
    cd.NOTIFY_ZASSETSU, cd.NOTIFY_ICHIRYU_MANBAI, cd.NOTIFY_SENJITSU = _ON[0], _ON[1], dict(_ON[2])

def _msg(y, m, d):
    fd = get_full_data(date(y, m, d), _dbs)   # 設定(ON/OFF)を切り替えて確かめるため、ここだけは使い回さない
    return fd, build_message(fd, "okayama")

TITLE_CASES = {   # 日付: (期待するタイトル, 本文に含まれるべき語)
    (2026, 11, 3): ("今日は「文化の日」（国民の祝日）", ["■国民の祝日「文化の日」"]),
    (2026, 10, 8): ("今日は二十四節気「寒露」の始まり", ["■二十四節気「寒露」の始まり", "鴻雁来"]),
    (2026, 10, 3): ("今日は七十二候「水始涸」（末候）の始まり", ["■七十二候「水始涸」（末候）の始まり"]),
    (2026, 3, 3): ("今日は「ひな祭り（上巳の節句）」（年中行事）", ["■年中行事「ひな祭り（上巳の節句）」"]),
    (2026, 10, 17): ("今日は「神嘗祭」（重要な祭日）", ["■重要な祭日「神嘗祭」"]),
    (2026, 10, 10): ("今日は「目の日」（記念日）", ["■記念日「目の日」"]),
    (2026, 5, 6): ("今日は「振替休日」（休日）", ["■休日「振替休日」"]),
    (2026, 1, 1): ("今日は「元日」（国民の祝日） ほか1件", ["■国民の祝日「元日」", "■重要な祭日「歳旦祭」"]),
}
report("日の干支: 十干の五行・陰陽、十二支の五行・動物が正しい",
       [cd.STEMS_INFO[k][1] for k in "甲乙丙丁戊己庚辛壬癸"] == list("木木火火土土金金水水")
       and [cd.STEMS_INFO[k][2] for k in "甲乙丙丁戊己庚辛壬癸"] == list("陽陰陽陰陽陰陽陰陽陰")
       and [cd.BRANCHES_INFO[k][2] for k in "子丑寅卯辰巳午未申酉戌亥"] == list("水土木木土火火土金金土水")
       and cd.BRANCHES_INFO["酉"][1] == "にわとり" and len(cd.KANSHI_USE) == 25)
_fd1 = get_full_data(date(2026, 10, 22), _dbs)
report("サイトのデータに、日の干支の説明(kanshi_info)が入り、従来の kanshi も残っている",
       _fd1["kanshi"] == "己巳" and _fd1["kanshi_info"]["name"] == "己巳" and "つちのとみ" in render_text(_fd1))

# =====================================================================
# 追加: 和暦・九星・潮汐・用語の解説ページ
# =====================================================================
import kyusei as _kyu
import os as _os, re as _re, html as _html, json as _json

# --- 和暦 ---
report("和暦: 令和元年(2019/5/1)・平成31年(2019/4/30)・平成元年(1989/1/8)・昭和64年(1989/1/7)・令和8年10月24日",
       ce.wareki_info(date(2019, 5, 1))["label"] == "令和元年5月1日" and ce.wareki_info(date(2019, 4, 30))["label"] == "平成31年4月30日"
       and ce.wareki_info(date(1989, 1, 8))["label"] == "平成元年1月8日" and ce.wareki_info(date(1989, 1, 7))["label"] == "昭和64年1月7日"
       and ce.wareki_info(date(2026, 10, 24))["label"] == "令和8年10月24日")

# --- 九星: 2026年の1年分を、公開されている日家九星の一覧(暦注カレンダー rekichu.com)の構造と照合 ---
#   一覧の構造: 1/1=三碧から6/18=九紫まで1日ずつ進み(陽遁)、6/19=九紫から12/15=一白まで1日ずつ戻り(陰遁)、
#   12/16=一白から再び進む(陽遁)。切り替わる日(6/18・6/19、12/15・12/16)は、同じ星が2日続く
def _kyusei_expected(d):
    if d <= date(2026, 6, 18):
        return ((d - date(2026, 1, 1)).days + 2) % 9 + 1
    if d <= date(2026, 12, 15):
        return 9 - ((d - date(2026, 6, 19)).days % 9)
    return ((d - date(2026, 12, 16)).days % 9) + 1
_bad = [d0 for d0 in (date(2026, 1, 1) + timedelta(days=i) for i in range(365)) if _kyu.day_star_number(d0) != _kyusei_expected(d0)]
report("日の九星: 2026年の365日すべてが、公開されている日家九星の一覧と一致する", not _bad, str(_bad[:3]))
_pts = {(2026, 10, 1): 4, (2026, 10, 2): 3, (2026, 10, 3): 2, (2026, 10, 22): 1, (2026, 10, 23): 9, (2026, 10, 24): 8, (2026, 12, 31): 7}
report("日の九星: 一覧に載っている10月1〜3日・22〜24日、12月31日の値と一致する", all(_kyu.day_star_number(date(*k)) == v for k, v in _pts.items()))
_ym = [((2026, 1, 1), 2, 1), ((2026, 1, 5), 2, 9), ((2026, 2, 3), 2, 9), ((2026, 2, 4), 1, 8), ((2026, 3, 5), 1, 7), ((2026, 5, 5), 1, 5),
       ((2026, 6, 6), 1, 4), ((2026, 10, 7), 1, 1), ((2026, 10, 8), 1, 9), ((2026, 11, 7), 1, 8), ((2026, 12, 7), 1, 7), ((2026, 12, 31), 1, 7)]
report("年の九星・月の九星: 2026年の12か所(立春・節入りの前後を含む)が、公開されている一覧と一致する",
       all((_kyu.year_star_number(date(*k)), _kyu.month_star_number(date(*k))) == (y, m) for k, y, m in _ym))
report("年の九星: 2000年=九紫・2024年=三碧・2025年=二黒・2026年=一白(立春以降)",
       [_kyu.year_star_number(date(y, 6, 1)) for y in (2000, 2024, 2025, 2026)] == [9, 3, 2, 1])
_ki2 = _kyu.kyusei_info(date(2026, 10, 24))
report("九星の情報: 2026/10/24=日:八白土星・月:九紫火星・年:一白水星(陰遁)",
       (_ki2["day"]["name"], _ki2["month"]["name"], _ki2["year"]["name"], _ki2["day"]["dun"]) == ("八白土星", "九紫火星", "一白水星", "陰遁") and _ki2["day"]["desc"])

# --- 潮汐(旧暦日による目安) ---
report("潮汐: 旧暦1〜30日のすべてに潮名があり、1周(15日)の並びが 大潮4・中潮3・小潮3・長潮1・若潮1・中潮3 になっている",
       sorted(cd.CHOUSEI_BY_KYUREKI_DAY) == list(range(1, 31)) and all(cd.CHOUSEI_BY_KYUREKI_DAY[i] in cd.CHOUSEI for i in range(1, 31))
       and [cd.CHOUSEI_BY_KYUREKI_DAY[i] for i in range(1, 16)] == ["大潮"] * 3 + ["中潮"] * 3 + ["小潮"] * 3 + ["長潮", "若潮"] + ["中潮"] * 3 + ["大潮"])
# 海上保安庁の潮汐表(関門海峡海上交通センター掲載の月別表)の潮名55日分(2021〜2025年)。旧暦日の表との一致数を確かめる
_TIDE = {
 (2025, 10, 1): "小潮", (2025, 10, 2): "長潮", (2025, 10, 3): "若潮", (2025, 10, 4): "中潮", (2025, 10, 5): "中潮", (2025, 10, 6): "大潮",
 (2025, 9, 1): "小潮", (2025, 9, 2): "長潮", (2025, 9, 3): "若潮", (2025, 9, 4): "中潮", (2025, 9, 5): "中潮", (2025, 9, 6): "中潮",
 (2025, 8, 1): "小潮", (2025, 8, 2): "小潮", (2025, 8, 3): "長潮", (2025, 8, 4): "若潮", (2025, 8, 5): "中潮",
 (2025, 1, 1): "大潮", (2025, 1, 2): "大潮", (2025, 1, 3): "中潮", (2025, 1, 4): "中潮", (2025, 1, 5): "中潮", (2025, 1, 6): "小潮",
 (2025, 2, 1): "中潮", (2025, 2, 2): "中潮", (2025, 2, 3): "中潮",
 (2021, 3, 1): "大潮", (2021, 3, 2): "中潮", (2021, 3, 3): "中潮", (2021, 3, 4): "中潮", (2021, 3, 5): "小潮", (2021, 3, 6): "小潮",
 (2024, 5, 1): "小潮", (2024, 5, 2): "小潮", (2024, 5, 3): "長潮", (2024, 5, 4): "若潮", (2024, 5, 5): "中潮", (2024, 5, 6): "中潮",
 (2021, 10, 1): "長潮", (2021, 10, 2): "若潮", (2021, 10, 3): "中潮", (2021, 10, 4): "中潮", (2021, 10, 5): "中潮", (2021, 10, 6): "大潮",
 (2023, 3, 1): "長潮", (2023, 3, 2): "若潮", (2023, 3, 3): "中潮", (2023, 3, 4): "中潮", (2023, 3, 5): "中潮", (2023, 3, 6): "大潮",
 (2023, 1, 1): "長潮", (2023, 1, 2): "若潮", (2023, 1, 3): "中潮", (2023, 1, 4): "中潮", (2023, 1, 5): "中潮",
}
from koyomi_engine import compute_kyuureki as _ck
_coarse = {"大潮": "大", "中潮": "中", "小潮": "小", "長潮": "小", "若潮": "小"}
_exact = _near = 0
for (y_, m_, d_), n_ in _TIDE.items():
    got = ce.tide_info(_ck(date(y_, m_, d_))["kyureki_day"])["name"]
    _exact += got == n_
    _near += _coarse[got] == _coarse[n_]
report(f"潮汐: 潮汐表の{len(_TIDE)}日のうち、旧暦日の表と一致するのは48日以上(実測 {_exact}日)、大・中・小で見ると52日以上(実測 {_near}日)",
       len(_TIDE) == 55 and _exact >= 48 and _near >= 52)

# --- 用語の解説ページ(public/guide): サイトに出る名前が、リンク先の見出しidとして、すべてある ---
_G = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "public", "guide")
def _ids(page):
    p = _os.path.join(_G, page + ".html")
    return {_html.unescape(x) for x in _re.findall(r'<section class="item" id="([^"]+)"', open(p, encoding="utf-8").read())} if _os.path.exists(p) else set()
_missing = {}
def _need(page, names):
    miss = [n for n in names if n not in _ids(page)]
    if miss:
        _missing[page] = miss[:5]
_need("rokuyo", list(cd.ROKUYO)); _need("kanshi", ce._kanshi_names()); _need("kyusei", [v[0] for v in cd.KYUSEI.values()])
_need("chousei", list(cd.CHOUSEI)); _need("senjitsu", list(cd.SENJITSU_DESC)); _need("ichiryumanbai", ["一粒万倍日"])
from koyomi_engine import SEKKI_NAMES as _SN, MOON_PHASE_NAMES as _MP
_need("sekki", [x[0] for x in _SN]); _need("getsurei", sorted(set(_MP.values())) + ["満ちていく月", "欠けていく月"])
_need("kou", [_json.loads(l)["kou_name"] for l in open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "kou_content_72.jsonl"), encoding="utf-8") if l.strip()])
_zs, _ev, _ho, _d = set(), set(), set(), date(2026, 1, 1)
while _d.year < 2036:
    _zs |= {x["name"] for x in ce.zassetsu_on(_d)}; _ev |= {x["name"] for x in ce.events_on(_d)}; _ho |= {x["name"] for x in ce.holidays_on(_d)}
    _d += timedelta(days=1)
_need("zassetsu", sorted(_zs)); _need("nenjugyoji", sorted(_ev)); _need("shukujitsu", sorted(_ho))
_need("saijitsu", [n for lst in cd.SAIJITSU_FIXED.values() for n, _ in lst] + [v[0] for v in cd.SAIJITSU_EQUINOX.values()])
_need("kinenbi", [x["name"] for r in ce._load_fixed_entries().values() for x in r if x.get("category", "記念日") == "記念日"])
_need("tenmon", ["月の満ち欠け", "日食・月食", "流星群"])
_need("kyureki", [_json.loads(l)["name"] for l in open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "kyureki_month_names.jsonl"), encoding="utf-8") if l.strip()])
_need("wareki", [n for n, _ in cd.WAREKI_ERAS])
report("用語の解説ページ: サイトに出る六曜・干支・九星・潮・選日・雑節・節気・七十二候・月の呼び名・祝日・行事・記念日などの名前が、すべてリンク先の見出しになっている", not _missing, str(_missing))
_dup = []
for _f in _os.listdir(_G) if _os.path.isdir(_G) else []:
    if _f.endswith(".html"):
        _t = _re.findall(r'<section class="item" id="([^"]+)"', open(_os.path.join(_G, _f), encoding="utf-8").read())
        if len(_t) != len(set(_t)):
            _dup.append(_f)
report("用語の解説ページ: 同じページの中で、見出しのidが重複していない(重複するとリンクがずれる)", not _dup, str(_dup))
_pages = {f[:-5] for f in _os.listdir(_G) if f.endswith(".html")} if _os.path.isdir(_G) else set()
_bad_links = []
for _f in sorted(_pages):
    for _href in _re.findall(r'href="([a-z]+)\.html', open(_os.path.join(_G, _f + ".html"), encoding="utf-8").read()):
        if _href not in _pages:
            _bad_links.append((_f, _href))
report("用語の解説ページ: ページ間のリンク先がすべて存在する(19ページ)", not _bad_links and len(_pages) == 19, f"{len(_pages)}ページ {_bad_links[:3]}")

_set_extra(False)   # 従来のきっかけ(雑節・選日・一粒万倍日を除く)だけで確かめる
for (y, m, dd), (title, words) in TITLE_CASES.items():
    fd, (t, b) = _msg(y, m, dd)
    report(f"通知タイトル {y}/{m}/{dd}: {title}", t == title and all(w in b for w in words) and "【岡山市】日の出" in b, f"{t}")
_restore_extra()

# 通知する日(2026〜2028年の全日)について、通知文が崩れていないか(雑節・選日・一粒万倍日も含めて)
bad, longest, most, days, d = [], 0, 0, 0, date(2026, 1, 1)
while d.year <= 2028:
    fd = _fd(d)
    if fd["reasons"]:
        days += 1 if d.year == 2026 else 0
        t, b = build_message(fd, "tokyo")
        longest, most = max(longest, len(t)), max(most, len(fd["reasons"]))
        if not t.startswith("今日は") or len(b.split("\n")) > 7 or any(not r["line"].startswith("■") for r in fd["reasons"]):
            bad.append((d, t))
    else:
        try:
            build_message(fd, "tokyo"); bad.append((d, "きっかけがないのに通知文が作れてしまう"))
        except ValueError:
            pass
    d += timedelta(days=1)
report(f"通知文: 2026〜2028年の全日付で、タイトルが「今日は…」で始まり本文も崩れない(最長タイトル{longest}字・1日のきっかけ最大{most}件)", not bad and longest <= 45, str(bad[:3]))

# =====================================================================
# 追加: 雑節・選日・一粒万倍日を通知のきっかけに加えた分
# =====================================================================
import collections
RANK = {"国民の祝日": 0, "休日": 0, "二十四節気": 1, "重要な祭日": 2, "年中行事": 3, "雑節": 4,
        "天赦日": 5, "記念日": 6, "七十二候": 7, "選日": 8, "一粒万倍日": 9}
def _rank(r):
    return RANK["天赦日"] if r["name"] == "天赦日" else RANK["一粒万倍日"] if r["name"] == "一粒万倍日" else RANK[r["label"]]

def _scan(years=(2026, 2027, 2028)):
    """全日付で、(雑節・選日・一粒万倍日の項目が通知のきっかけに入っているか)と、(きっかけの並び順)を調べる"""
    missing, order_bad, extra_days, all_days = [], [], set(), set()
    d = date(years[0], 1, 1)
    while d.year <= years[-1]:
        fd = _fd(d)
        names = {(r["label"], r["name"]) for r in fd["reasons"]}
        want = [("雑節", z["name"]) for z in fd["zassetsu"]] + [("選日", z["name"]) for z in fd["senjitsu"]] \
               + ([("選日", "一粒万倍日")] if fd["ichiryu_manbai"] else [])
        if want:
            extra_days.add(d)
        missing += [(d, w) for w in want if w not in names]
        ranks = [_rank(r) for r in fd["reasons"]]
        if ranks != sorted(ranks):
            order_bad.append((d, [r["short"] for r in fd["reasons"]]))
        if fd["reasons"]:
            all_days.add(d)
        d += timedelta(days=1)
    return missing, order_bad, extra_days, all_days

missing, order_bad, extra_days, all_days = _scan()
report("雑節・選日・一粒万倍日(2026〜2028年のすべての該当日)が、通知のきっかけに入っている", not missing, str(missing[:3]))
report("きっかけの並び順: 祝日 → 節気 → 祭日 → 年中行事 → 雑節 → 天赦日 → 記念日 → 七十二候 → 選日 → 一粒万倍日(全日付)", not order_bad, str(order_bad[:2]))

# 2026年の通知する日数: 従来のきっかけだけの日数と、雑節・選日・一粒万倍日を足した日数
def _days_2026():
    s, d = set(), date(2026, 1, 1)
    while d.year == 2026:
        if build_reasons(_fd(d)):   # 今の設定(ON/OFF)でのきっかけ。暦の計算は使い回す
            s.add(d)
        d += timedelta(days=1)
    return s
all_2026 = _days_2026()
_set_extra(False); base_2026 = _days_2026(); _restore_extra()
extra_2026 = {d for d in extra_days if d.year == 2026}
report("通知する日数 2026年(従来のきっかけだけ) = 139日", len(base_2026) == 139,
       f"{len(base_2026)}日  ← 139日と合わないときは、memorial_days.jsonl が整理前の古い版でないか確認する")
report("通知する日数 2026年(雑節・選日・一粒万倍日を加えた) = 従来の日数 + 新しく加わった日数", all_2026 == base_2026 | extra_2026, f"{len(all_2026)}日")
print(f"      (2026年: 従来 {len(base_2026)}日 → 加えたあと {len(all_2026)}日 / 加わった日 {len(all_2026 - base_2026)}日)")

# 種類ごとのON/OFF: OFFにした種類だけが、きっかけから外れる
def _labels_2026(kind_filter):
    out, d = collections.Counter(), date(2026, 1, 1)
    while d.year == 2026:
        for r in build_reasons(_fd(d)):
            if kind_filter(r):
                out[r["name"]] += 1
        d += timedelta(days=1)
    return out
is_sen = lambda r: r["label"] == "選日"
for key in ("不成就日", "寅の日", "巳の日", "己巳の日", "天赦日"):
    cd.NOTIFY_SENJITSU[key] = False
    off = _labels_2026(is_sen)
    cd.NOTIFY_SENJITSU[key] = True
    on = _labels_2026(is_sen)
    report(f"設定: 選日「{key}」だけOFFにすると、その通知だけが外れる", key not in off and off[key] == 0 and on[key] > 0
           and all(off[k] == on[k] for k in on if k != key))
cd.NOTIFY_ICHIRYU_MANBAI = False
off = _labels_2026(is_sen); cd.NOTIFY_ICHIRYU_MANBAI = True
report("設定: 一粒万倍日だけOFFにすると、その通知だけが外れる", "一粒万倍日" not in off)
cd.NOTIFY_ZASSETSU = False
off = _labels_2026(lambda r: r["label"] == "雑節"); cd.NOTIFY_ZASSETSU = True
report("設定: 雑節をOFFにすると、雑節の通知が外れる", not off)
_restore_extra()

# 代表的な日の通知文(雑節・選日)。きっかけが日付だけで決まる日を選んでいる
NEW_CASES = {
    (2026, 10, 22): ("今日は「己巳の日」（選日）", ["■選日「己巳の日」"]),
    (2026, 3, 20): ("今日は「春分の日」（国民の祝日） ほか5件", ["■雑節「彼岸の中日」", "ほか1件"]),
}
for (y, m, dd), (title, words) in NEW_CASES.items():
    fd, (t, b) = _msg(y, m, dd)
    report(f"通知タイトル {y}/{m}/{dd}: {title}", t == title and all(w in b for w in words) and "【岡山市】日の出" in b, f"{t}")

print()
print("結果: すべてOK" if NG == 0 else f"結果: NGが{NG}件あります")
sys.exit(1 if NG else 0)
