# -*- coding: utf-8 -*-
"""
backfill_new_markets.py — 从 rins.my/huat3 拉4家新公司全历史 → 并入 slim_data.json
新市场: 沙巴(EE) / 9龙(NL) / 砂拉越(CS) / 山打根(STC)
只增不覆盖; 运行前请先备份 slim_data.json
"""
import urllib.request, re, json, sys, time, io, os

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
SLIM = os.path.join(BASE, "slim_data.json")

NEW_MARKETS = [("沙巴", "EE"), ("9龙", "NL"), ("砂拉越", "CS"), ("山打根", "STC")]

def scrape_huat3(code, fromyear=1988):
    url = f"https://rins.my/huat3?t={code}&d=&p=&fromyear={fromyear}&month=0"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    rows = re.findall(
        r'<tr data-type="' + code + r'">\s*<td>(\d{4}-\d{2}-\d{2})</td>\s*<td>([^<]*)</td>'
        r'\s*<td[^>]*>(\d{4})[^<]*</td>\s*<td[^>]*>(\d{4})[^<]*</td>\s*<td[^>]*>(\d{4})[^<]*</td>', html)
    return rows  # [(date, draw, n1, n2, n3)] newest-first

def main():
    with open(SLIM, encoding="utf-8") as f:
        sd = json.load(f)

    for name, code in NEW_MARKETS:
        rows = scrape_huat3(code)
        if not rows:
            print(f"{name}({code}): 抓取失败, 跳过"); continue
        # 去重 (以日期为准), 保持新→旧
        seen = set(); clean = []
        for d, draw, n1, n2, n3 in rows:
            if d in seen: continue
            seen.add(d)
            clean.append(f"{d},{draw.strip()},{n1},{n2},{n3}")
        existing = {}
        if name in sd["DB"]:
            for line in sd["DB"][name].strip().split("\n"):
                p = line.split(",")
                if len(p) >= 5: existing[p[0]] = line
        # 只增不覆盖
        added = 0
        for line in clean:
            d = line.split(",")[0]
            if d not in existing:
                existing[d] = line; added += 1
        merged = sorted(existing.values(), key=lambda l: l.split(",")[0], reverse=True)
        sd["DB"][name] = "\n".join(merged)
        print(f"{name}({code}): 抓到{len(clean)}期, 新增{added}, 库内共{len(merged)}期 ({merged[-1].split(',')[0]} ~ {merged[0].split(',')[0]})")
        time.sleep(2)

    sd["_meta"]["description"] = sd["_meta"].get("description", "") + " +4新市场(rins.my)"
    tmp = SLIM + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sd, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, SLIM)
    print("slim_data.json 已更新, 大小:", os.path.getsize(SLIM))

if __name__ == "__main__":
    main()
