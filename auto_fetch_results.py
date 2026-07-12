# -*- coding: utf-8 -*-
"""
auto_fetch_results.py — 自动抓取五市场 4D 开奖成绩 → auto_results.json

数据源: live4d2u.net (首页 = 最新一期; /past-results POST datepicker=YYYY-MM-DD = 指定日期)
市场映射与 lottery.html V37 解析器一致: 万能/多多/跑马(Damacai)/新加坡/豪龙
输出: auto_results.json  {updated_at, source, draws:[{market,date,draw,nums:[头,二,三]}]}
用法: python auto_fetch_results.py            # 抓今天 + 自动补漏最近7天
      python auto_fetch_results.py --backfill 30   # 补漏最近30天
lottery.html 打开时会自动读取 auto_results.json 并合并(只增不覆盖)。
"""
import requests, re, json, sys, time, os, io
from datetime import date, datetime, timedelta

def _force_utf8_stdout():
    # Windows 控制台默认编码打不出中文, 统一强制 UTF-8
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(BASE_DIR, "auto_results.json")
LOG_FILE = os.path.join(BASE_DIR, "auto_fetch.log")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
HOME_URL = "https://www.live4d2u.net/"
PAST_URL = "https://www.live4d2u.net/past-results"

# 市场区块起始标记(兼容首页/历史页的写法差异); 顺序即扫描顺序
MARKET_MARKERS = [
    ("万能",   [r"Magnum 4D\b"]),
    ("跑马",   [r"Da ?Ma ?Cai 1\+3D", r"Damacai 1\+3D"]),
    ("多多",   [r"SportsToto 4D\b", r"Sports Toto 4D\b"]),
    ("豪龙",   [r"Grand Dragon (?:Lotto )?4D"]),
    ("新加坡", [r"Singapore (?:Pools )?4D"]),
]
# 这些区块是干扰项, 用作边界防止跨块误读
BOUNDARY_MARKERS = [
    r"Magnum 4D\b", r"Da ?Ma ?Cai 1\+3D", r"Damacai 1\+3D", r"SportsToto 4D\b",
    r"Sports Toto 4D\b", r"Grand Dragon (?:Lotto )?4D", r"Singapore (?:Pools )?4D",
    r"SportsToto 5D", r"Da ?Ma ?Cai 3\+3D", r"Magnum Life", r"Magnum Jackpot",
    r"Singapore Toto", r"Sabah", r"Sarawak", r"STC 4D", r"Supreme Toto",
    r"Sandakan 4D", r"Special CashSweep", r"Perdana Lottery", r"Lucky HariHari",
]

def _find_block_start(text, pats):
    """市场名也出现在页面标题/导航里; 只有后面紧跟完整日期(Date: dd-mm-yyyy)的才是真成绩区块
    (历史页导航区有个空的 "Date: " 日期选择框, 所以必须要求日期数字)"""
    candidates = []
    for pat in pats:
        for m in re.finditer(pat, text):
            candidates.append(m.start())
    for pos in sorted(candidates):
        if re.search(r"Date:\s*\|?\s*\d{2}-\d{2}-\d{4}", text[pos:pos + 150]):
            return pos
    return None

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        # 日志超 200KB 截半
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 200_000:
            with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
                tail = f.read()[-100_000:]
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write(tail)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass

def html_to_text(html):
    t = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<style[^>]*>.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", "|", t)
    t = re.sub(r"&nbsp;?", " ", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\|[\s|]*\|", "|", t)
    return t

def parse_page(html):
    """从一页 HTML 解析五市场 → [{market,date,draw,nums}]"""
    text = html_to_text(html)
    # 所有边界位置
    bounds = []
    for pat in BOUNDARY_MARKERS:
        for m in re.finditer(pat, text):
            bounds.append(m.start())
    bounds = sorted(set(bounds))

    out = []
    for market, pats in MARKET_MARKERS:
        start = _find_block_start(text, pats)
        if start is None:
            continue
        nxt = [b for b in bounds if b > start]
        end = nxt[0] if nxt else min(start + 900, len(text))
        block = text[start:end]

        dm = re.search(r"Date:\s*\|?\s*(\d{2})-(\d{2})-(\d{4})", block)
        if not dm:
            continue
        d = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}"
        rm = re.search(r"Draw No:?\s*\|?\s*([0-9/]+)", block)
        draw = rm.group(1) if rm else ""
        n1 = re.search(r"1st[^|]*\|\s*(\d{4})\b", block)
        n2 = re.search(r"2nd[^|]*\|\s*(\d{4})\b", block)
        n3 = re.search(r"3rd[^|]*\|\s*(\d{4})\b", block)
        if n1 and n2 and n3:
            entry = {"market": market, "date": d, "draw": draw,
                     "nums": [n1.group(1), n2.group(1), n3.group(1)]}
            sp, cs = _parse_sp_cs(block)
            if sp: entry["sp"] = sp
            if cs: entry["cs"] = cs
            out.append(entry)
    return out

def _parse_sp_cs(block):
    """特别奖/安慰奖: Special 标签到 Consolation 标签之间 / Consolation 到奖金区之间的 4 位数.
    ----/**** 是空位或被源站遮住的号码, 自动跳过(多多偶尔有几个 **** 抓不到)."""
    sp, cs = [], []
    m_sp = re.search(r"Special", block)
    m_cs = re.search(r"Consolation", block)
    if m_sp and m_cs and m_sp.start() < m_cs.start():
        seg = block[m_sp.end():m_cs.start()]
        sp = re.findall(r"\b(\d{4})\b", seg)[:13]
    if m_cs:
        seg = block[m_cs.end():]
        # 安慰奖后面跟着积宝奖金(Jackpot/RM), 先截断再取号
        cut = re.search(r"Jackpot|RM\s", seg)
        if cut:
            seg = seg[:cut.start()]
        cs = re.findall(r"\b(\d{4})\b", seg)[:13]
    return sp, cs

def fetch_home(sess):
    r = sess.get(HOME_URL, timeout=30)
    r.raise_for_status()
    return parse_page(r.content.decode("utf-8", "replace"))

def fetch_past(sess, d):
    r = sess.post(PAST_URL, data={"datepicker": d.strftime("%Y-%m-%d")}, timeout=30)
    r.raise_for_status()
    draws = parse_page(r.content.decode("utf-8", "replace"))
    # 历史页只保留请求日期的记录, 防止页面夹带别天数据
    return [x for x in draws if x["date"] == d.strftime("%Y-%m-%d")]

def load_existing():
    try:
        with open(OUT_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("draws", [])
    except (OSError, ValueError):
        return []

def main():
    backfill_days = 7
    if "--backfill" in sys.argv:
        i = sys.argv.index("--backfill")
        if i + 1 < len(sys.argv):
            backfill_days = max(0, min(60, int(sys.argv[i + 1])))

    sess = requests.Session()
    sess.headers.update(UA)

    existing = load_existing()
    seen = {(x["market"], x["date"]) for x in existing}
    # 某天已有 ≥4 个市场 = 抓齐了; 不足则可能当晚只发布了一半, 补漏时重查
    date_counts = {}
    for x in existing:
        date_counts[x["date"]] = date_counts.get(x["date"], 0) + 1
    added = []

    # 1) 首页 = 最新成绩
    try:
        for x in fetch_home(sess):
            if (x["market"], x["date"]) not in seen:
                added.append(x); seen.add((x["market"], x["date"]))
        log(f"首页抓取 OK, 新增 {len(added)} 条")
    except Exception as e:
        log(f"首页抓取失败: {type(e).__name__}: {e}")

    # 2) 补漏: 最近 N 天里记录不足 4 个市场的日期 → 查历史页(豪龙每天开, 有漏必现形)
    today = date.today()
    for i in range(1, backfill_days + 1):
        d = today - timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        if date_counts.get(ds, 0) >= 4:
            continue
        try:
            time.sleep(2)
            got = fetch_past(sess, d)
            n = 0
            for x in got:
                if (x["market"], x["date"]) not in seen:
                    added.append(x); seen.add((x["market"], x["date"])); n += 1
            log(f"补漏 {ds}: {n} 条")
        except Exception as e:
            log(f"补漏 {ds} 失败: {type(e).__name__}: {e}")

    if not added and existing:
        log("无新数据, 文件保持不变")
        return

    # 3) 合并写出: 按市场保留最近 120 期, 日期新→旧
    merged = existing + added
    by_market = {}
    for x in merged:
        by_market.setdefault(x["market"], []).append(x)
    final = []
    for mk, arr in by_market.items():
        arr.sort(key=lambda x: x["date"], reverse=True)
        final.extend(arr[:120])
    final.sort(key=lambda x: (x["date"], x["market"]), reverse=True)

    tmp = OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now().isoformat(timespec="seconds"),
                   "source": "live4d2u.net", "draws": final}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_FILE)
    log(f"写出 {OUT_FILE}: 共 {len(final)} 条 (本次新增 {len(added)})")

if __name__ == "__main__":
    _force_utf8_stdout()
    try:
        main()
    except Exception as e:
        log(f"致命错误: {type(e).__name__}: {e}")
        sys.exit(1)
