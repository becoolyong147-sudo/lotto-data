# -*- coding: utf-8 -*-
"""
merge_results.py — 合并两份 auto_results.json(本机抓的 + 云端抓的),谁的新成绩都不丢
用法:
  python merge_results.py --git-conflict      # git rebase/merge 冲突时用: 读 :2: 和 :3: 两个版本, 合并写回 auto_results.json
  python merge_results.py --from-origin       # 把云端 origin/main 的版本合并进本机文件(抓之前用, 本机未推送的也不会丢)
  python merge_results.py a.json b.json out.json
规则: 按 (市场, 日期) 合并; 同一期两边都有时, 取资料更完整的(特别奖/安慰奖多的);
      头二三不一样时取 updated_at 较新的那一份(源站补全后会纠正)。
"""
import json, sys, subprocess, os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "auto_results.json")


def load_text(t):
    try:
        return json.loads(t)
    except Exception:
        return {"draws": []}


def score(x):
    return len(x.get("sp") or []) + len(x.get("cs") or [])


def merge(a, b):
    ua, ub = a.get("updated_at", ""), b.get("updated_at", "")
    newer, older = (a, b) if ua >= ub else (b, a)
    by = {}
    for x in older.get("draws", []):
        by[(x.get("market"), x.get("date"))] = x
    for x in newer.get("draws", []):
        k = (x.get("market"), x.get("date"))
        o = by.get(k)
        if o is None:
            by[k] = x
            continue
        if (o.get("nums") or [])[:3] != (x.get("nums") or [])[:3]:
            by[k] = x                      # 头二三不同: 信较新的
        elif score(x) >= score(o):
            by[k] = x
        else:
            by[k] = o
    draws = sorted(by.values(), key=lambda x: (x.get("date", ""), x.get("market", "")))
    out = dict(newer)
    out["updated_at"] = max(ua, ub)
    out["draws"] = draws
    return out


def git_show(stage):
    r = subprocess.run(["git", "show", ":%d:auto_results.json" % stage], cwd=BASE, capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""


def main():
    a = sys.argv[1:]
    if a and a[0] == "--git-conflict":
        A, B = load_text(git_show(2)), load_text(git_show(3))
        out = merge(A, B)
        dst = OUT
    elif a and a[0] == "--from-origin":
        r = subprocess.run(["git", "show", "origin/main:auto_results.json"], cwd=BASE, capture_output=True)
        A = load_text(r.stdout.decode("utf-8", "replace") if r.returncode == 0 else "")
        try:
            B = load_text(open(OUT, encoding="utf-8").read())
        except Exception:
            B = {"draws": []}
        out = merge(A, B); dst = OUT
    elif len(a) >= 3:
        A = load_text(open(a[0], encoding="utf-8").read()); B = load_text(open(a[1], encoding="utf-8").read())
        out = merge(A, B); dst = a[2]
    else:
        print(__doc__); return
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, dst)
    print("合并完成: 共 %d 期" % len(out["draws"]))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
