// 读本机成绩: slim_data.json(历史头二三) + auto_results.json(最近成绩, 含特别奖)
// 只看头二三+特别奖, 不看安慰奖; 山打根不用
import fs from "node:fs";
import path from "node:path";

const BASE = path.resolve(import.meta.dirname, "..");
const SLIM = path.join(BASE, "slim_data.json");
const AUTO = path.join(BASE, "auto_results.json");
const SKIP = new Set(["山打根"]);

let cache = null;
let cacheMtime = 0;

function mtime(f) {
  try { return fs.statSync(f).mtimeMs; } catch { return 0; }
}

function load() {
  const m = Math.max(mtime(SLIM), mtime(AUTO));
  if (cache && m === cacheMtime) return cache;

  // market -> date -> { date, draw, top: [头,二,三], sp: [...] }
  const byMarket = {};
  const put = (market, date, draw, top, sp) => {
    if (SKIP.has(market)) return;
    const mk = (byMarket[market] ??= {});
    const cur = mk[date];
    if (!cur) mk[date] = { date, draw, top, sp: sp ?? [] };
    else if (sp?.length && !cur.sp.length) cur.sp = sp;
  };

  try {
    const auto = JSON.parse(fs.readFileSync(AUTO, "utf8"));
    for (const d of auto.draws ?? []) put(d.market, d.date, d.draw, d.nums, d.sp);
  } catch (e) {
    console.error("读 auto_results.json 失败:", e.message);
  }
  try {
    const slim = JSON.parse(fs.readFileSync(SLIM, "utf8"));
    for (const [market, text] of Object.entries(slim.DB ?? {})) {
      for (const line of text.split("\n")) {
        const [date, draw, a, b, c] = line.trim().split(",");
        if (date && a) put(market, date, draw, [a, b, c], null);
      }
    }
  } catch (e) {
    console.error("读 slim_data.json 失败:", e.message);
  }

  const markets = {};
  for (const [market, dates] of Object.entries(byMarket)) {
    markets[market] = Object.values(dates).sort((x, y) => y.date.localeCompare(x.date));
  }
  cache = markets;
  cacheMtime = m;
  return cache;
}

export function marketNames() {
  return Object.keys(load());
}

const sortDigits = (n) => n.split("").sort().join("");

// 查一个4位号码以前开过没有: 正号(完全一样) + 打包(数字一样顺序不同)
export function lookupNumber(number, market) {
  const num = String(number).replace(/\D/g, "");
  if (num.length !== 4) return { error: "号码要4位数字" };
  const data = load();
  const key = sortDigits(num);
  const names = market ? [market] : Object.keys(data);
  const prizeName = ["头奖", "二奖", "三奖"];
  const exact = [];
  const box = [];

  for (const mk of names) {
    for (const d of data[mk] ?? []) {
      const hits = [];
      d.top.forEach((n, i) => hits.push([n, prizeName[i]]));
      d.sp.forEach((n) => hits.push([n, "特别奖"]));
      for (const [n, prize] of hits) {
        if (!n) continue;
        if (n === num) exact.push({ market: mk, date: d.date, prize });
        else if (sortDigits(n) === key) box.push({ market: mk, date: d.date, prize, number: n });
      }
    }
  }
  const newest = (a, b) => b.date.localeCompare(a.date);
  exact.sort(newest);
  box.sort(newest);
  return {
    number: num,
    note: "头二三奖查的是全部历史; 特别奖只有 2026-06 之后的记录",
    exact_count: exact.length,
    exact_recent: exact.slice(0, 15),
    box_count: box.length,
    box_recent: box.slice(0, 15),
  };
}

// 最新一期成绩
export function latestResults(market) {
  const data = load();
  const names = market ? [market] : Object.keys(data);
  return names
    .filter((mk) => data[mk]?.length)
    .map((mk) => {
      const d = data[mk][0];
      return { market: mk, date: d.date, draw: d.draw, 头奖: d.top[0], 二奖: d.top[1], 三奖: d.top[2], 特别奖: d.sp };
    });
}
