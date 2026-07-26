# -*- coding: utf-8 -*-
"""
auto_fetch_results.py — 自动抓取九市场 4D 开奖成绩 → auto_results.json

数据源: rins.my (2026-07-27 起, 与用户 Excel 同源; 旧源 live4d2u 已弃用)
  - huat5?t=<代号>  : 每市场最近3期, 含 特别奖13 + 安慰奖10 (---- = 空位自动跳过)
  - huat3?t=<代号>&fromyear=YYYY : 该市场从某年至今全历史(仅头二三奖), 用于补漏
九市场: 万能M 跑马PMP 多多ST 新加坡SG 豪龙GD 沙巴EE 9龙NL 砂拉越CS 山打根STC
  (豪龙/9龙 天天开, 其余每周约3次)
输出: auto_results.json {updated_at, source, draws:[{market,date,draw,nums,sp,cs}]}
用法: python auto_fetch_results.py                 # 抓最新 + 补漏最近7天
      python auto_fetch_results.py --backfill 30   # 补漏最近30天
lottery.html 打开时会自动读取 auto_results.json 并合并(只增不覆盖)。
"""
import requests, re, json, sys, time, os, io
from datetime import date, datetime, timedelta

def _force_utf8_stdout():
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(BASE_DIR, "auto_results.json")
LOG_FILE = os.path.join(BASE_DIR, "auto_fetch.log")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
HUAT5 = "https://rins.my/huat5"   # 最近3期 + sp/cs
HUAT3 = "https://rins.my/huat3"   # 全历史, 仅头二三

# 市场 → rins 代号 (顺序即抓取顺序)
MARKETS = [
    ("万能", "M"), ("跑马", "PMP"), ("多多", "ST"), ("新加坡", "SG"),
    ("豪龙", "GD"), ("沙巴", "EE"), ("9龙", "NL"), ("砂拉越", "CS"), ("山打根", "STC"),
]

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 200_000:
            with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
                tail = f.read()[-100_000:]
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write(tail)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass

def fetch_huat5(sess, market, code):
    """最近3期(含 sp/cs) → [{market,date,draw,nums,sp,cs}]"""
    r = sess.get(HUAT5, params={"t": code, "d": "", "p": "", "fromyear": date.today().year, "month": 0}, timeout=30)
    r.raise_for_status()
    html = r.content.decode("utf-8", "replace")
    out = []
    # 每期一块: header(date, weekday, draw) + results 表
    blocks = re.split(r'<div class="header">', html)[1:]
    for blk in blocks:
        hm = re.search(r"<span>(\d{4}-\d{2}-\d{2})</span>\s*<span>[^<]*</span>\s*<span>([^<]*)</span>", blk)
        if not hm:
            continue
        d, draw = hm.group(1), hm.group(2).strip()
        tbl = re.search(r'<table class="results">(.*?)</table>', blk, re.S)
        if not tbl:
            continue
        # 行分组: 头二三 | 分隔 | 特别奖(13) | 分隔 | 安慰奖(10); ---- = 空位
        groups, cur = [], []
        for row in re.findall(r"<tr>(.*?)</tr>", tbl.group(1), re.S):
            cells = re.findall(r"<td[^>]*>([^<]*)</td>", row)
            nums = [c.strip() for c in cells if re.fullmatch(r"\d{4}", c.strip())]
            if nums:
                cur.extend(nums)
            elif cur:
                groups.append(cur); cur = []
        if cur:
            groups.append(cur)
        if not groups or len(groups[0]) < 3:
            continue
        entry = {"market": market, "date": d, "draw": draw, "nums": groups[0][:3]}
        if len(groups) > 1 and groups[1]:
            entry["sp"] = groups[1][:13]
        if len(groups) > 2 and groups[2]:
            entry["cs"] = groups[2][:13]
        out.append(entry)
    return out

def fetch_huat3_range(sess, market, code, fromdate):
    """fromdate(含)之后的所有开奖(仅头二三) → [{market,date,draw,nums}]"""
    r = sess.get(HUAT3, params={"t": code, "d": "", "p": "", "fromyear": fromdate.year, "month": 0}, timeout=60)
    r.raise_for_status()
    html = r.content.decode("utf-8", "replace")
    rows = re.findall(
        r'<tr data-type="' + code + r'">\s*<td>(\d{4}-\d{2}-\d{2})</td>\s*<td>([^<]*)</td>'
        r'\s*<td[^>]*>(\d{4})[^<]*</td>\s*<td[^>]*>(\d{4})[^<]*</td>\s*<td[^>]*>(\d{4})[^<]*</td>', html)
    lo = fromdate.strftime("%Y-%m-%d")
    return [{"market": market, "date": d, "draw": draw.strip(), "nums": [n1, n2, n3]}
            for d, draw, n1, n2, n3 in rows if d >= lo]

def load_existing():
    try:
        with open(OUT_FILE, encoding="utf-8") as f:
            return json.load(f).get("draws", [])
    except (OSError, ValueError):
        return []

def main():
    backfill_days = 7
    if "--backfill" in sys.argv:
        i = sys.argv.index("--backfill")
        if i + 1 < len(sys.argv):
            backfill_days = max(0, min(365, int(sys.argv[i + 1])))

    sess = requests.Session()
    sess.headers.update(UA)

    existing = load_existing()
    by_key = {(x["market"], x["date"]): x for x in existing}
    added, spcs_filled = 0, 0

    # 1) huat5: 每市场最近3期(含 sp/cs); 已有条目只补缺失的 sp/cs 不动 nums
    for market, code in MARKETS:
        try:
            for x in fetch_huat5(sess, market, code):
                k = (x["market"], x["date"])
                if k not in by_key:
                    by_key[k] = x; added += 1
                else:
                    old = by_key[k]
                    for f in ("sp", "cs"):
                        if f in x and not old.get(f):
                            old[f] = x[f]; spcs_filled += 1
            time.sleep(1.5)
        except Exception as e:
            log(f"huat5 {market} 失败: {type(e).__name__}: {e}")
    log(f"huat5 最新抓取 OK: 新增 {added} 条, 补 sp/cs {spcs_filled} 处")

    # 2) huat3 补漏: 一次拉整段历史, 补最近 N 天缺的日期(仅头二三)
    if backfill_days > 0:
        cutoff = date.today() - timedelta(days=backfill_days)
        bf = 0
        for market, code in MARKETS:
            have = {d for (m, d) in by_key if m == market}
            try:
                rows = fetch_huat3_range(sess, market, code, cutoff)
                for x in rows:
                    if x["date"] not in have:
                        by_key[(market, x["date"])] = x; bf += 1
                time.sleep(1.5)
            except Exception as e:
                log(f"huat3 补漏 {market} 失败: {type(e).__name__}: {e}")
        log(f"huat3 补漏({backfill_days}天) OK: 补回 {bf} 条")
        added += bf

    if not added and not spcs_filled and existing:
        log("无新数据, 文件保持不变")
        return

    # 3) 合并写出: 按市场保留最近 120 期, 日期新→旧
    by_market = {}
    for x in by_key.values():
        by_market.setdefault(x["market"], []).append(x)
    final = []
    for mk, arr in by_market.items():
        arr.sort(key=lambda x: x["date"], reverse=True)
        final.extend(arr[:120])
    final.sort(key=lambda x: (x["date"], x["market"]), reverse=True)

    tmp = OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now().isoformat(timespec="seconds"),
                   "source": "rins.my", "draws": final}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_FILE)
    log(f"写出 {OUT_FILE}: 共 {len(final)} 条 (新增 {added}, 补sp/cs {spcs_filled})")

if __name__ == "__main__":
    _force_utf8_stdout()
    try:
        main()
    except Exception as e:
        log(f"致命错误: {type(e).__name__}: {e}")
        sys.exit(1)
