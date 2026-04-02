#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析文件列表中文件夹项的结构"""

import sys
import json
import time

sys.path.insert(0, r'C:\Users\admin\.claude\plugins\xianfeng-search\scripts')

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9225')
    page = browser.contexts[0].pages[0]

    # 导航到有子文件夹的目录
    page.goto('https://fsdvaugca1.phenixfin.com/drive/folder/KWScfw3uNlqicMdCCsKvJ1JQmCd')
    time.sleep(5)

    # 获取所有文件列表项
    items = page.query_selector_all('[role="item"]')
    print(f"找到 {len(items)} 个列表项\n")

    for i, item in enumerate(items[:5]):
        try:
            html = item.evaluate('el => el.outerHTML')
            print(f"--- 项目 {i} ---")
            print(html[:800])
            print()

            # 查找链接
            links = item.query_selector_all('a')
            for link in links:
                href = link.get_attribute('href')
                print(f"  链接: {href}")

            # 查找 data-type
            data_type = item.evaluate('''
                el => {
                    const typeEl = el.querySelector('[data-type]');
                    return typeEl ? typeEl.getAttribute('data-type') : null;
                }
            ''')
            print(f"  data-type: {data_type}")

        except Exception as e:
            print(f"错误: {e}")

    browser = None