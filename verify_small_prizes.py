# -*- coding: utf-8 -*-
"""抓完后的总验收: python verify_small_prizes.py
对 small_prizes.json 的每一条检查: 特别奖/安慰奖个数、重复、与历史库(slim_data.json + auto_results.json)头二三是否一致"""
import json, io, os, collections, sys
B = os.path.dirname(os.path.abspath(__file__))
sp = json.load(io.open(os.path.join(B, 'small_prizes.json'), encoding='utf-8'))['draws']
slim = json.load(io.open(os.path.join(B, 'slim_data.json'), encoding='utf-8'))['DB']
auto = json.load(io.open(os.path.join(B, 'auto_results.json'), encoding='utf-8'))['draws']
ours = {}
for mk, txt in slim.items():          # slim_data.json 的 DB 是字符串: 每行  日期,期号,头奖,二奖,三奖
    if not isinstance(txt, str):
        continue
    for line in txt.splitlines():
        parts = line.strip().split(",")
        if len(parts) >= 5 and len(parts[0]) == 10:
            ours[(mk, parts[0])] = [v.zfill(4) for v in parts[2:5]]
for x in auto: ours[(x['market'], x['date'])] = [str(v).zfill(4) for v in x['nums'][:3]]
print('历史库可对照期数:', len(ours))
by = collections.defaultdict(lambda: dict(n=0, s10=0, c10=0, match=0, mism=0, nolib=0, dup=0, first=None, last=None))
seen = set(); bad = []
for r in sp:
    k = (r['market'], r['date']); b = by[r['market']]; b['n'] += 1
    if k in seen: b['dup'] += 1
    seen.add(k)
    b['first'] = min(b['first'] or r['date'], r['date']); b['last'] = max(b['last'] or r['date'], r['date'])
    if len(r['sp']) == 10: b['s10'] += 1
    if len(r['cs']) == 10: b['c10'] += 1
    o = ours.get(k)
    if o is None: b['nolib'] += 1
    elif o == [str(v).zfill(4) for v in r['nums']]: b['match'] += 1
    else: b['mism'] += 1; bad.append((r['market'], r['date'], r['nums'], o))
print('\n%-5s %6s %8s %8s %8s %8s %8s %6s  %s' % ('市场', '条数', '特别=10', '安慰=10', '头二三对', '头二三错', '库无此期', '重复', '起止'))
tot = collections.Counter()
for mk, b in sorted(by.items()):
    print('%-5s %6d %8d %8d %8d %8d %8d %6d  %s~%s' % (mk, b['n'], b['s10'], b['c10'], b['match'], b['mism'], b['nolib'], b['dup'], b['first'], b['last']))
    for k2 in ('n', 's10', 'c10', 'match', 'mism', 'nolib', 'dup'): tot[k2] += b[k2]
print('合计', dict(tot))
print('\n头二三对不上的(前10):'); [print(' ', x) for x in bad[:10]]
