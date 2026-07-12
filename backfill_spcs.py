# -*- coding: utf-8 -*-
"""
backfill_spcs.py — 回补 2021 年起五市场完整成绩(头二三 + 特别奖 + 安慰奖)→ spcs_history.json

- 数据源: live4d2u.net /past-results (POST datepicker=YYYY-MM-DD), 每天一个请求, 限速 ~2.5s
- 断点续跑: 已扫描日期记录在输出文件 scanned_dates 里, 中断后重跑自动接着来
- 交叉验证: 头二三奖逐期与 slim_data.json 历史库比对, 不一致记入 mismatches(数据照存)
- 连续失败 10 次自动停止(疑似被源站限制), 稍后重跑即可续
用法: python backfill_spcs.py [--from 2021-01-01] [--limit 300]
日志: spcs_backfill.log
"""
import requests, json, sys, os, time, io, random
from datetime import date, datetime, timedelta

from auto_fetch_results import parse_page, UA, PAST_URL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(BASE_DIR, "spcs_history.json")
LOG_FILE = os.path.join(BASE_DIR, "spcs_backfill.log")
SLIM_FILE = os.path.join(BASE_DIR, "slim_data.json")

START_DEFAULT = "2021-01-01"
SLEEP_BASE = 2.5
MAX_CONSEC_FAIL = 10
SAVE_EVERY = 50  # 每扫描50天落盘一次


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_state():
    try:
        with open(OUT_FILE, encoding="utf-8") as f:
            st = json.load(f)
        st.setdefault("scanned_dates", [])
        st.setdefault("draws", [])
        st.setdefault("mismatches", [])
        return st
    except (OSError, ValueError):
        return {"source": "live4d2u.net", "scanned_dates": [], "draws": [], "mismatches": []}


def save_state(st):
    st["updated_at"] = datetime.now().isoformat(timespec="seconds")
    tmp = OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT_FILE)


def load_db_index():
    """slim_data 历史库 → {(market,date): [n1,n2,n3]} 用于交叉验证"""
    idx = {}
    try:
        slim = json.load(open(SLIM_FILE, encoding="utf-8"))
        for mk, txt in slim.get("DB", {}).items():
            for line in txt.split("\n"):
                p = line.split(",")
                if len(p) >= 5:
                    idx[(mk, p[0])] = [p[2], p[3], p[4]]
    except (OSError, ValueError) as e:
        log(f"警告: 无法读取 slim_data.json 做交叉验证: {e}")
    return idx


def main():
    start = START_DEFAULT
    limit = None
    if "--from" in sys.argv:
        start = sys.argv[sys.argv.index("--from") + 1]
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    st = load_state()
    scanned = set(st["scanned_dates"])
    seen = {(x["market"], x["date"]) for x in st["draws"]}
    dbidx = load_db_index()

    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    todo = []
    d = date.today()
    while d >= d0:  # 新→旧, 中断时较新的数据已先到手
        ds = d.strftime("%Y-%m-%d")
        if ds not in scanned:
            todo.append(d)
        d -= timedelta(days=1)
    if limit:
        todo = todo[:limit]
    if not todo:
        log("没有待扫描日期, 已全部完成")
        return

    log(f"待扫描 {len(todo)} 天 ({todo[-1]} ~ {todo[0]}), 预计 {len(todo)*3/60:.0f} 分钟")
    sess = requests.Session()
    sess.headers.update(UA)

    consec_fail = 0
    done = 0
    for d in todo:
        ds = d.strftime("%Y-%m-%d")
        time.sleep(SLEEP_BASE + random.uniform(0, 1))
        try:
            r = sess.post(PAST_URL, data={"datepicker": ds}, timeout=30)
            html = r.content.decode("utf-8", "replace")
            if r.status_code != 200 or "Past" not in html:
                raise RuntimeError(f"异常响应 status={r.status_code} len={len(html)}")
            draws = [x for x in parse_page(html) if x["date"] == ds]
            consec_fail = 0
        except Exception as e:
            consec_fail += 1
            log(f"{ds} 失败({consec_fail}连败): {type(e).__name__}: {e}")
            if consec_fail >= MAX_CONSEC_FAIL:
                log(f"连续失败 {MAX_CONSEC_FAIL} 次, 疑似被源站限制 — 停止, 稍后重跑会自动续")
                break
            continue

        n_new = 0
        for x in draws:
            key = (x["market"], x["date"])
            if key in seen:
                continue
            ref = dbidx.get(key)
            if ref is not None and ref != x["nums"]:
                st["mismatches"].append({"market": x["market"], "date": ds,
                                         "scraped": x["nums"], "db": ref})
                log(f"⚠️ {ds} {x['market']} 头二三与历史库不一致: 抓={x['nums']} 库={ref}")
            st["draws"].append(x)
            seen.add(key)
            n_new += 1
        scanned.add(ds)
        st["scanned_dates"] = sorted(scanned)
        done += 1
        if done % 25 == 0:
            log(f"进度 {done}/{len(todo)} ({ds}) · 累计 {len(st['draws'])} 期 · 不一致 {len(st['mismatches'])}")
        if done % SAVE_EVERY == 0:
            save_state(st)

    save_state(st)
    log(f"本轮结束: 扫描 {done} 天, 总 {len(st['draws'])} 期, 待扫剩余 {len(todo)-done} 天, 不一致 {len(st['mismatches'])} 期")


if __name__ == "__main__":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
