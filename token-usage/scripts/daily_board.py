#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查看过去7天每日排行榜"""
import json
import subprocess
import sys
import io
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CACHE_DIR = Path.home() / '.claude' / 'token-usage' / '.cache'
TOKEN_FILE = Path.home() / '.claude' / 'token-usage' / '.token'
CONFIG_FILE = Path.home() / '.claude' / 'token-usage' / 'config.json'
REPO_URL = 'https://github.com/sjerold/token-board.git'

def get_token():
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding='utf-8').strip()
    return ''

def fmt_tokens(n):
    if n >= 1000000:
        return f'{n/1000000:.1f}M'
    elif n >= 1000:
        return f'{n/1000:.0f}K'
    return str(n)

token = get_token()
if not token:
    print('需要先配置Token')
    exit(1)

token_url = REPO_URL.replace('https://', f'https://{token}@')

if not CACHE_DIR.exists():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'clone', '--depth', '1', '-b', 'main', token_url, '.'],
                   cwd=CACHE_DIR, capture_output=True)
else:
    subprocess.run(['git', 'remote', 'set-url', 'origin', token_url],
                   cwd=CACHE_DIR, capture_output=True)
    subprocess.run(['git', 'fetch', 'origin'], cwd=CACHE_DIR, capture_output=True)
    subprocess.run(['git', 'reset', '--hard', 'origin/main'],
                   cwd=CACHE_DIR, capture_output=True)

data_dir = CACHE_DIR / 'data'
all_data = []
if data_dir.exists():
    for f in data_dir.glob('*.json'):
        try:
            all_data.append(json.loads(f.read_text(encoding='utf-8')))
        except:
            pass

user_id = ''
if CONFIG_FILE.exists():
    try:
        user_id = json.loads(CONFIG_FILE.read_text()).get('user_id', '')
    except:
        pass

# 过去7天
today = datetime.now()
dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

print()
print('🏆 过去7天Token排行榜 (按日期分组)')
print('=' * 60)

for date in sorted(dates, reverse=True):
    board = []
    for data in all_data:
        daily = data.get('daily', {})
        if date in daily:
            d = daily[date]
            board.append({
                'user_id': data.get('user_id'),
                'user_name': data.get('user_name', '匿名'),
                'tokens': d['input'] + d['output'],
                'calls': d['calls']
            })

    if board:
        board.sort(key=lambda x: x['tokens'], reverse=True)
        print(f'\n📅 {date}')
        print('-' * 50)
        for i, e in enumerate(board[:5]):
            is_me = ' ← 你' if e['user_id'] == user_id else ''
            print(f'  #{i+1} {e["user_name"]:<12} {fmt_tokens(e["tokens"]):>8} tokens ({e["calls"]}次){is_me}')
    else:
        print(f'\n📅 {date}')
        print('-' * 50)
        print('  无数据')

print()