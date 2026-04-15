#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - DOM方式抓取

通过滚动页面和DOM解析获取文档内容。
"""

import sys
import time
import re
from typing import Dict, List

from .table_parser import build_markdown_table


def scroll_and_extract(page, wait_time: int = 10) -> str:
    """
    滚动页面加载内容并提取

    Args:
        page: Playwright页面对象
        wait_time: 等待时间

    Returns:
        提取的内容
    """
    print("正在滚动加载完整内容...", file=sys.stderr)

    # 等待编辑器加载
    try:
        page.wait_for_selector('[contenteditable]', timeout=15000)
    except:
        pass

    # 点击文档区域确保焦点
    try:
        page.click('[contenteditable]', timeout=2000)
        time.sleep(0.5)
    except:
        pass

    # 等待网络空闲
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass

    # 滚动到底部加载虚拟列表内容
    for _ in range(30):
        page.keyboard.press('PageDown')
        time.sleep(0.15)

    # 滚回顶部
    page.keyboard.press('Control+Home')
    time.sleep(1)

    # 方法1: 直接获取编辑器 innerText
    editor_selectors = [
        '[contenteditable]',
        '.editor',
        '[class*="editor"]',
        '.doc-content',
    ]
    for sel in editor_selectors:
        try:
            editor = page.query_selector(sel)
            if editor:
                text = editor.evaluate('el => el.innerText')
                if text and len(text.strip()) > 50:
                    print(f"  编辑器内容({sel}): {len(text)} 字符", file=sys.stderr)
                    return text.strip()
        except:
            continue

    # 方法2: 获取整个页面文本
    try:
        body_text = page.evaluate('document.body.innerText')
        if body_text and len(body_text) > 50:
            print(f"  页面内容: {len(body_text)} 字符", file=sys.stderr)
            return body_text
    except:
        pass

    # 方法3: 滚动收集可见块
    collected_text = []
    for _ in range(30):
        visible = page.evaluate('''
            () => {
                const blocks = document.querySelectorAll('[data-block-id], [contenteditable] p, [contenteditable] div');
                return Array.from(blocks)
                    .filter(b => {
                        const r = b.getBoundingClientRect();
                        return r.top >= 0 && r.top <= window.innerHeight;
                    })
                    .map(b => b.innerText?.trim())
                    .filter(t => t && t.length > 3)
                    .join('\\n');
            }
        ''')
        if visible:
            collected_text.append(visible)

        page.keyboard.press('PageDown')
        time.sleep(0.2)

    if collected_text:
        unique = list(dict.fromkeys(collected_text))
        merged = '\n\n'.join(unique)
        if len(merged) > 50:
            print(f"  收集内容: {len(merged)} 字符", file=sys.stderr)
            return merged

    # 备用：直接提取编辑器内容
    return extract_editor_content(page)


def extract_editor_content(page) -> str:
    """从编辑器提取内容 - 多种备用方案"""
    selectors = [
        '[contenteditable]',
        '[contenteditable="true"]',
        '.editor',
        '.editor-content',
        '.doc-content',
        '[class*="editor"]',
        '[class*="content-area"]',
        '.suite-editor',
        '[data-lark-record-format]',
    ]

    for selector in selectors:
        try:
            editor = page.query_selector(selector)
            if editor:
                text = editor.evaluate('el => el.textContent || el.innerText')
                if text and len(text.strip()) > 50:
                    return clean_content(text.strip())
        except:
            continue

    # 最后尝试：提取整个页面的主要文本
    try:
        main_content = page.evaluate('''
            () => {
                const main = document.querySelector('main') || document.querySelector('[role="main"]') || document.body;
                const paragraphs = main.querySelectorAll('p, div[data-block-id], span[data-block-id], h1, h2, h3, li');
                return Array.from(paragraphs)
                    .map(p => p.textContent?.trim())
                    .filter(t => t && t.length > 10)
                    .join('\\n\\n');
            }
        ''')
        if main_content and len(main_content) > 100:
            return clean_content(main_content)
    except:
        pass

    return ""


def extract_title(page) -> str:
    """提取文档标题"""
    selectors = ['.doc-title', '.document-title', '.title', 'h1', '[class*="title"]']

    for selector in selectors:
        try:
            elem = page.query_selector(selector)
            if elem:
                title = elem.inner_text().strip()
                if title:
                    return title
        except:
            continue

    # 从页面标题提取
    try:
        page_title = page.title()
        return re.sub(r'\s*[-|]\s*(飞书|Lark|Feishu).*$', '', page_title).strip()
    except:
        pass

    return "未命名文档"


def clean_content(content: str) -> str:
    """清理内容"""
    lines = [line.strip() for line in content.split('\n') if line.strip()]

    # 移除过短的行
    cleaned = [l for l in lines if len(l) > 3 or l.startswith(('-', '*', '•', '1.', '2.', '3.'))]

    content = '\n'.join(cleaned)

    # 截断过长内容
    if len(content) > 50000:
        content = content[:50000] + '\n\n... (内容已截断)'

    return content


def extract_tables_from_dom(page) -> Dict[str, str]:
    """
    使用 DOM 方式提取表格内容

    Returns:
        字典: {table_index: markdown_table_string}
    """
    try:
        table_selectors = [
            '.table-scrollable-content',
            'table.table',
            'table',
        ]

        result = {}
        table_index = 0

        for selector in table_selectors:
            try:
                table_containers = page.locator(selector).all()
                print(f"  [DOM表格] 选择器 '{selector}' 找到 {len(table_containers)} 个元素", file=sys.stderr)
            except Exception as e:
                continue

            for idx, table_container in enumerate(table_containers):
                try:
                    table_container.wait_for(state='visible', timeout=5000)

                    first_row = table_container.locator('tr').first
                    first_cell = first_row.locator('td, th').first

                    try:
                        first_cell.wait_for(state='visible', timeout=3000)
                    except:
                        continue

                    table_container.scroll_into_view_if_needed()
                    time.sleep(0.5)

                    rows = table_container.locator('tr').all()
                    if not rows:
                        continue

                    table_rows = []

                    for i, row in enumerate(rows):
                        cells = row.locator('td, th').all()
                        if not cells:
                            continue

                        row_data = []

                        for cell in cells:
                            try:
                                cell.scroll_into_view_if_needed()
                            except:
                                pass

                            try:
                                text = cell.inner_text().strip()
                                text = text.replace('\n', '<br>').replace('|', '\\|')
                            except:
                                text = ''

                            row_data.append(text)

                        if row_data and any(c for c in row_data):
                            table_rows.append(row_data)

                    if len(table_rows) >= 2 and any(c for row in table_rows for c in row):
                        md_table = build_markdown_table(table_rows)
                        if md_table:
                            result[table_index] = md_table
                            table_index += 1

                except:
                    continue

        print(f"  [DOM表格] 共提取 {len(result)} 个表格", file=sys.stderr)
        return result

    except Exception as e:
        print(f"  [DOM表格] 提取失败: {e}", file=sys.stderr)
        return {}


def extract_all_tables_by_scrolling(page, block_map: Dict) -> List[str]:
    """
    通过滚动到每个表格位置来提取所有表格内容

    Args:
        page: Playwright 页面对象
        block_map: API 返回的 block_map

    Returns:
        表格 Markdown 字符串列表
    """
    tables = []

    table_block_ids = []
    for block_id, block in block_map.items():
        if block.get('data', {}).get('type') == 'table':
            table_block_ids.append(block_id)

    if not table_block_ids:
        return tables

    print(f"  [DOM表格] 找到 {len(table_block_ids)} 个表格块，逐个滚动提取...", file=sys.stderr)

    for i, block_id in enumerate(table_block_ids):
        try:
            found = page.evaluate(f'''
                () => {{
                    const selectors = [
                        '[data-block-id="{block_id}"]',
                        '[data-id="{block_id}"]',
                        'table[data-block-id="{block_id}"]'
                    ];

                    for (const sel of selectors) {{
                        const elem = document.querySelector(sel);
                        if (elem) {{
                            elem.scrollIntoView({{ behavior: 'instant', block: 'center' }});
                            return {{ found: true, method: sel }};
                        }}
                    }}

                    const allTables = document.querySelectorAll('table.table, .table-scrollable-content');
                    if (allTables.length > {i}) {{
                        allTables[{i}].scrollIntoView({{ behavior: 'instant', block: 'center' }});
                        return {{ found: true, method: 'by_index' }};
                    }}

                    return {{ found: false, reason: 'no_table_element' }};
                }}
            ''')

            if found and found.get('found'):
                time.sleep(1)

                visible_tables = extract_tables_from_dom(page)
                for idx, table_md in visible_tables.items():
                    if table_md not in tables:
                        tables.append(table_md)

        except:
            continue

    print(f"  [DOM表格] 滚动提取完成，共 {len(tables)} 个表格", file=sys.stderr)
    return tables