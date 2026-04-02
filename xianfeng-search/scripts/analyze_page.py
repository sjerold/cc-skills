#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析有文档的文件夹页面结构"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright

# 使用环境变量或默认测试URL
TEST_URL = os.environ.get('XIANFENG_TEST_URL', 'https://example.feishu.cn/drive/folder/test')

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9225')
    page = browser.contexts[0].pages[0]

    # 导航到有文档的文件夹
    page.goto(TEST_URL)
    time.sleep(5)  # 等待加载

    # 获取文件列表区域的HTML
    result = page.evaluate('''
        () => {
            let results = {};

            // 查找主要内容区域右侧的文件列表
            const rightPanel = document.querySelector('.sc-gSQGeZ') || document.querySelector('[class*="explorer"]');
            if (rightPanel) {
                results['right_panel'] = {
                    class: rightPanel.className,
                    html: rightPanel.outerHTML.substring(0, 3000)
                };
            }

            // 查找所有可能的文件列表项
            const selectors = [
                '[role=item]',
                '[role="listitem"]',
                '.file-list-item',
                '.doc-item',
                'tr[data-id]',
                'div[data-id]',
                '[data-e2e*=file]',
                '[data-e2e*=item]',
                '[data-e2e*=grid]',
                '[data-e2e*=list]',
                '.grid-item',
                '.list-item',
            ];

            for (const sel of selectors) {
                const items = document.querySelectorAll(sel);
                if (items.length > 0) {
                    results[sel] = {
                        count: items.length,
                        samples: Array.from(items).slice(0, 3).map(i => i.outerHTML.substring(0, 500))
                    };
                }
            }

            // 查找所有带 data-e2e 属性的元素
            const e2eElements = document.querySelectorAll('[data-e2e]');
            results['all_data_e2e'] = Array.from(e2eElements).map(e => e.getAttribute('data-e2e'));

            return results;
        }
    ''')

    print(json.dumps(result, ensure_ascii=False, indent=2))
    browser = None