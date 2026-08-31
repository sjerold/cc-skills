#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理状态文件中指定域名的记录"""
import json
import sys

domain = sys.argv[1] if len(sys.argv) > 1 else 'sh.mof.gov.cn'
p = r'C:\Users\admin\Downloads\web_article_fetcher\.fetched_urls.json'
s = json.load(open(p, encoding='utf-8'))
before = len(s['urls'])
for k, v in list(s['urls'].items()):
    if domain in (v.get('url') or ''):
        s['urls'].pop(k)
json.dump(s, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'清理 {before - len(s["urls"])} 条，剩余 {len(s["urls"])}')
