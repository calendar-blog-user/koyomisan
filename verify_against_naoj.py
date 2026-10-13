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
from render_koyomi import build_message, get_full_data, load_databases
_dbs = load_databases()

def _msg(y, m, d):
    fd = get_full_data(date(y, m, d), _dbs)
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
for (y, m, dd), (title, words) in TITLE_CASES.items():
    fd, (t, b) = _msg(y, m, dd)
    report(f"通知タイトル {y}/{m}/{dd}: {title}", t == title and all(w in b for w in words) and "【岡山市】日の出" in b, f"{t}")

# 通知する日(2026〜2028年の全日)について、通知文が崩れていないか
bad, longest, most, days, d = [], 0, 0, 0, date(2026, 1, 1)
while d.year <= 2028:
    fd = get_full_data(d, _dbs)
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
report("通知する日数 2026年 = 139日(今回の変更で通知の頻度は変わらない)", days == 139, str(days))

print()
print("結果: すべてOK" if NG == 0 else f"結果: NGが{NG}件あります")
sys.exit(1 if NG else 0)
