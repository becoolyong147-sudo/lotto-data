#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from collections import Counter

with open('slim_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

magnum_data = data['DB']['豪龙']
lines = [l.strip() for l in magnum_data.split('\n') if l.strip()]

print('=' * 70)
print('豪龙 Latest 20 Draws')
print('=' * 70)

for i, line in enumerate(lines[:20]):
    parts = line.split(',')
    if len(parts) >= 5:
        date, draw, p1, p2, p3 = parts[0], parts[1], parts[2], parts[3], parts[4]
        print(f'{i+1:2d}. {date} Draw {draw:>3s} | 头:{p1} 二:{p2} 三:{p3}')

# 统计频率
print('\n' + '=' * 70)
print('Digit Frequency (Last 20 draws)')
print('=' * 70)

all_nums = []
for line in lines[:20]:
    parts = line.split(',')
    if len(parts) >= 5:
        p1, p2, p3 = parts[2], parts[3], parts[4]
        all_nums.extend(list(p1) + list(p2) + list(p3))

freq = Counter(all_nums)
for digit in sorted('0123456789'):
    count = freq.get(digit, 0)
    bar = '█' * count
    print(f'  {digit}: {bar} ({count})')

print('\n今日新成绩（需更新）:')
print('  2026-07-04: 1574 5870 3723')
