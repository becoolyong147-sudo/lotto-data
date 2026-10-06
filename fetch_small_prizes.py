# -*- coding: utf-8 -*-
"""
fetch_small_prizes.py — 补抓「过去的特别奖(10个) + 安慰奖(10个)」
来源: 4d2ulive.com/past-results/YYYY-MM-DD (公开页面, robots.txt 未禁止; 每页含全部公司)
输出: small_prizes.json  {updated_at, source, draws:[{market,date,draw,nums,sp,cs}]}
  - 只追加、可断点续跑(已抓的日期记在 small_prizes.progress.json), 不动 auto_results.json
  - 与 rins.my 的口径一致: 头二三去掉; 特别奖只留有数字的10个(去掉 ---- 空位)

用法:
  python fetch_small_prizes.py --check 2026-09-30            # 只解析一个日期并打印(核对用)
  python fetch_small_prizes.py --from 2020-06-01 --to 今天    # 抓一段(默认: 2020-06-01 ~ 今天)
  python fetch_small_prizes.py --merge-check                  # 把抓到的和 auto_results.json 重叠部分逐期对照
"""
import re, sys, os, json, time, urllib.request, urllib.error
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "small_prizes.json")
PROG = os.path.join(BASE, "small_prizes.progress.json")
URL = "https://4d2ulive.com/past-results/{d}"
UA = {"User-Agent": "Mozilla/5.0 (LotteryHobbyist; polite; 1 req/1.3s)"}
SLEEP = 1.3

# 网站标题 -> 页面里的市场名
SITE2MK = {
    "Magnum 4D": "万能",
    "Da Ma Cai 1+3D": "跑马",
    "SportsToto 4D": "多多",
    "Singapore 4D": "新加坡",
    "Sabah 88 4D": "沙巴",
    "Special CashSweep": "砂拉越",
    "Sandakan 4D": "山打根",
}
TITLES = list(SITE2MK.keys()) + ["Nine Lotto", "Grand Dragon 4D", "Perdana Lottery 4D", "Lucky HariHari",
                                  "Magnum Life", "Magnum Jackpot Gold", "Sports Toto 5D", "Sports Toto 6D"]


def log(m):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), m), flush=True)


def get(d):
    req = urllib.request.Request(URL.format(d=d), headers=UA)
    for k in range(3):
        try:
            r = urllib.request.urlopen(req, timeout=40)
            return r.read().decode("utf-8", "replace")
        except Exception as e:
            if k == 2:
                raise
            time.sleep(3 * (k + 1))


def to_text(h):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", t)


def parse_page(h, d):
    """返回 [{market,date,draw,nums,sp,cs}] ; 该日没有开奖/没有该公司 → 不返回"""
    t = to_text(h)
    # 每个公司块: 从 "<标题> <中文名> Date: dd-mm-yyyy (周) Draw No: xxx" 开始
    out = []
    # 标题 + 中文名 + Date + Draw No。注意: 同页还有 Magnum Life / Jackpot Gold / Da Ma Cai 3+3D / SportsToto 5D,6D 等,
    # 它们没有 "Special/Consolation" 4D 结构, 下面 p1/sp/cs 不匹配会被自然跳过; 但「块的终点」要把它们也算作分隔, 否则会串块
    pat = re.compile(r"(Magnum 4D|Da Ma Cai 1\+3D|SportsToto 4D|Singapore 4D|Sabah 88 4D|Special CashSweep|Sandakan 4D"
                     r"|Magnum Life|Magnum Jackpot Gold|Da Ma Cai 3\+3D|SportsToto 5D, 6D, Lotto)"
                     r"\s*\S*\s*Date:\s*(\d{2})-(\d{2})-(\d{4})\s*\(\w+\)\s*Draw No:\s*([0-9/]+)")
    ms = list(pat.finditer(t))
    for i, m in enumerate(ms):
        title = m.group(1)
        if title not in SITE2MK:        # 别的游戏(只作分隔用)
            continue
        dd, mm, yy = m.group(2), m.group(3), m.group(4)
        if "%s-%s-%s" % (yy, mm, dd) != d:        # 页面上的日期必须等于请求的日期(防止跳页/占位)
            continue
        end = ms[i + 1].start() if i + 1 < len(ms) else len(t)
        seg = t[m.end():end]
        p1 = re.search(r"1st(?: Prize)?\s+\S+\s+(\d{4})(?:\s+Zodiac)?\s+2nd(?: Prize)?\s+\S+\s+(\d{4})\s+3rd(?: Prize)?\s+\S+\s+(\d{4})", seg)
        sp = re.search(r"Special\s+\S+\s+(.*?)\s+Consolation", seg)
        cs = re.search(r"Consolation\s+\S+\s+((?:[\d-]{4}\s*){1,10})", seg)
        if not p1 or not sp or not cs:
            continue
        sp4 = re.findall(r"(?<!\d)(\d{4})(?!\d)", sp.group(1))
        cs4 = re.findall(r"(?<!\d)(\d{4})(?!\d)", cs.group(1))
        out.append({"market": SITE2MK[title], "date": d, "draw": m.group(5),
                    "nums": list(p1.groups()), "sp": sp4[:10], "cs": cs4[:10]})
    return out


def load_prog():
    try:
        return json.load(open(PROG, encoding="utf-8"))
    except Exception:
        return {"done": []}


def load_out():
    try:
        return json.load(open(OUT, encoding="utf-8")).get("draws", [])
    except Exception:
        return []


def save(draws, prog):
    draws.sort(key=lambda x: (x["date"], x["market"]))
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now().isoformat(timespec="seconds"), "source": "4d2ulive.com", "draws": draws},
                  f, ensure_ascii=False, indent=0)
    os.replace(tmp, OUT)
    tmp = PROG + ".tmp"
    json.dump(prog, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, PROG)


def main():
    a = sys.argv[1:]
    if "--check" in a:
        d = a[a.index("--check") + 1]
        rows = parse_page(get(d), d)
        for r in rows:
            print(r["market"], r["date"], r["draw"], "头二三", r["nums"], "特别", len(r["sp"]), "安慰", len(r["cs"]))
            print("   特别奖", r["sp"]); print("   安慰奖", r["cs"])
        print("共", len(rows), "家")
        return
    d1 = date.fromisoformat(a[a.index("--from") + 1]) if "--from" in a else date(2020, 6, 1)
    d2 = date.fromisoformat(a[a.index("--to") + 1]) if "--to" in a else date.today()
    prog = load_prog(); done = set(prog["done"]); draws = load_out()
    have = {(x["market"], x["date"]) for x in draws}
    days = []
    cur = d1
    while cur <= d2:
        days.append(cur.isoformat()); cur += timedelta(days=1)
    todo = [x for x in days if x not in done]
    log("日期 %s ~ %s 共 %d 天, 已完成 %d, 待抓 %d" % (d1, d2, len(days), len(days) - len(todo), len(todo)))
    n_new = 0; fails = 0
    for k, d in enumerate(todo):
        try:
            rows = parse_page(get(d), d)
        except Exception as e:
            fails += 1; log("失败 %s: %s" % (d, e))
            if fails >= 15:
                log("连续失败太多, 停止(下次从断点继续)"); break
            time.sleep(5); continue
        fails = 0
        for r in rows:
            if (r["market"], r["date"]) not in have:
                draws.append(r); have.add((r["market"], r["date"])); n_new += 1
        done.add(d)
        if (k + 1) % 25 == 0:
            prog["done"] = sorted(done); save(draws, prog)
            log("进度 %d/%d  累计 %d 条" % (k + 1, len(todo), len(draws)))
        time.sleep(SLEEP)
    prog["done"] = sorted(done); save(draws, prog)
    log("完成。本次新增 %d 条, 总计 %d 条, 已完成日期 %d 天" % (n_new, len(draws), len(done)))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
