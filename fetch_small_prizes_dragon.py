# -*- coding: utf-8 -*-
"""
fetch_small_prizes_dragon.py — 补豪龙(Grand Dragon 4D) / 9龙(Nine Lotto) 的特别奖(10个)+安慰奖
来源: 4d2ulive.com/grand-dragon-4d-all/page/N  与  4d2ulive.com/nine-lotto/page/N (每页6期, 公开页面)
结果合并进 small_prizes.json(只追加这两个市场, 原有其它市场不动); 原子写入, 可断点续跑(记在 small_prizes_dragon.progress.json)
用法:  python fetch_small_prizes_dragon.py            # 两个市场全部页
       python fetch_small_prizes_dragon.py --check 豪龙 1   # 只解析一页并打印
"""
import re, sys, os, json, time, urllib.request
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "small_prizes.json")
PROG = os.path.join(BASE, "small_prizes_dragon.progress.json")
SRC = {"豪龙": "https://4d2ulive.com/grand-dragon-4d-all/page/{n}", "9龙": "https://4d2ulive.com/nine-lotto/page/{n}"}
FIRST = {"豪龙": "https://4d2ulive.com/grand-dragon-4d-all", "9龙": "https://4d2ulive.com/nine-lotto"}
UA = {"User-Agent": "Mozilla/5.0 (LotteryHobbyist; polite; 1 req/1.5s)"}
SLEEP = 1.5


def log(m):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), m), flush=True)


def get(u):
    last = None
    for k in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40).read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(3 * (k + 1))
    raise last


def to_text(h):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t.replace("&nbsp;", " "))


PAT = re.compile(r"(Grand Dragon 4D|Nine Lotto)(?:\s*豪龙)?\s*Date:\s*(\d{2})-(\d{2})-(\d{4})\s*\(\w+\)(?:\s*Draw No:\s*([0-9/]+))?\s*"
                 r"1st Prize\s*\S+\s*(\d{4})\s*2nd Prize\s*\S+\s*(\d{4})\s*3rd Prize\s*\S+\s*(\d{4})\s*"
                 r"Special\s*\S+\s*(.*?)\s*Consolation\s*\S+\s*((?:[\d-]{4}\s*){1,10})")


def parse(h, mk):
    t = to_text(h)
    out = []
    for m in PAT.finditer(t):
        dd, mm, yy = m.group(2), m.group(3), m.group(4)
        sp = re.findall(r"(?<!\d)(\d{4})(?!\d)", m.group(9))[:10]
        cs = re.findall(r"(?<!\d)(\d{4})(?!\d)", m.group(10))[:10]
        out.append({"market": mk, "date": "%s-%s-%s" % (yy, mm, dd), "draw": m.group(5) or "",
                    "nums": [m.group(6), m.group(7), m.group(8)], "sp": sp, "cs": cs})
    return out


def load_all():
    try:
        return json.load(open(OUT, encoding="utf-8"))
    except Exception:
        return {"draws": []}


def save(doc):
    doc["draws"].sort(key=lambda x: (x["date"], x["market"]))
    doc["updated_at"] = datetime.now().isoformat(timespec="seconds")
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=0)
    os.replace(tmp, OUT)


def main():
    a = sys.argv[1:]
    if "--check" in a:
        mk = a[a.index("--check") + 1]; n = int(a[a.index("--check") + 2])
        u = FIRST[mk] if n <= 1 else SRC[mk].format(n=n)
        rows = parse(get(u), mk)
        for r in rows:
            print(r["market"], r["date"], r["draw"], r["nums"], "特别", len(r["sp"]), "安慰", len(r["cs"]))
        print("共", len(rows), "期")
        return
    try:
        prog = json.load(open(PROG, encoding="utf-8"))
    except Exception:
        prog = {"done": {}}
    doc = load_all()
    have = {(x["market"], x["date"]) for x in doc["draws"]}
    added = 0
    for mk in ("豪龙", "9龙"):
        # 页数: 先读第1页里的最大页码
        h1 = get(FIRST[mk]); pages = max([int(x) for x in re.findall(r"/page/(\d+)", h1)] + [1])
        log("%s 共约 %d 页" % (mk, pages))
        done = set(prog["done"].get(mk, []))
        empty_streak = 0
        for n in range(1, pages + 1):
            if n in done:
                continue
            try:
                rows = parse(h1 if n == 1 else get(SRC[mk].format(n=n)), mk)
            except Exception as e:
                log("失败 %s p%d: %s" % (mk, n, e)); continue
            for r in rows:
                if (r["market"], r["date"]) not in have:
                    doc["draws"].append(r); have.add((r["market"], r["date"])); added += 1
            done.add(n)
            empty_streak = empty_streak + 1 if not rows else 0
            if n % 20 == 0:
                prog["done"][mk] = sorted(done); json.dump(prog, open(PROG, "w", encoding="utf-8")); save(doc)
                log("%s 进度 %d/%d · 累计新增 %d" % (mk, n, pages, added))
            if empty_streak >= 5:
                log("%s 连续空页, 停" % mk); break
            time.sleep(SLEEP)
        prog["done"][mk] = sorted(done); json.dump(prog, open(PROG, "w", encoding="utf-8")); save(doc)
    log("完成。新增 %d 条, 总计 %d 条" % (added, len(doc["draws"])))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
