#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
表格抓取模块 - 抓取飞书表格内容
"""

import time
from typing import Dict


def fetch_sheets_content(page, doc_url: str, result: Dict) -> Dict:
    """
    抓取飞书表格内容

    Args:
        page: Playwright页面对象
        doc_url: 表格URL
        result: 结果字典

    Returns:
        更新后的结果字典
    """
    from content_fetcher import _extract_title, _clean_content

    try:
        # 等待表格加载
        time.sleep(5)

        # 提取表格标题
        title = _extract_title(page)
        result['title'] = title

        # 尝试多种方式提取表格内容
        all_content = []

        # 方法1: 获取所有单元格文本
        content = _extract_cells(page)
        if content:
            all_content.append(content)

        # 方法2: 滚动表格收集内容
        content = _scroll_and_collect(page)
        if content:
            all_content.append(content)

        # 方法3: 获取整个表格容器
        content = _extract_table_container(page)
        if content:
            all_content.append(content)

        # 合并所有内容
        if all_content:
            best_content = max(all_content, key=len)
            result['content'] = _clean_content(best_content)
            result['success'] = True
            result['length'] = len(result['content'])
            print(f"表格抓取成功: {len(result['content'])} 字符", file=__import__('sys').stderr)
        else:
            result['error'] = '未能提取表格内容'

    except Exception as e:
        result['error'] = str(e)
        print(f"表格抓取失败: {e}", file=__import__('sys').stderr)

    return result


def _extract_cells(page) -> str:
    """方法1: 获取所有单元格文本"""
    try:
        cell_texts = page.evaluate('''
            () => {
                let cells = [];
                const selectors = [
                    '[data-cell-id]',
                    '.cell',
                    '[role="gridcell"]',
                    '[role="cell"]',
                    'td',
                    'th'
                ];

                for (const sel of selectors) {
                    const elems = document.querySelectorAll(sel);
                    if (elems.length > 0) {
                        elems.forEach(e => {
                            const text = e.innerText?.trim();
                            if (text && text.length > 0) {
                                cells.push(text);
                            }
                        });
                        if (cells.length > 10) break;
                    }
                }
                return cells;
            }
        ''')
        if cell_texts and len(cell_texts) > 5:
            print(f"  单元格提取: 找到 {len(cell_texts)} 个单元格", file=__import__('sys').stderr)
            return '\n'.join(cell_texts)
    except Exception as e:
        print(f"  单元格提取失败: {e}", file=__import__('sys').stderr)
    return None


def _scroll_and_collect(page) -> str:
    """方法2: 滚动表格并收集可见内容"""
    try:
        collected_cells = []

        # 点击表格区域
        try:
            page.click('[role="grid"]', timeout=2000)
        except:
            pass

        # 横向和纵向滚动收集内容
        for _ in range(10):
            visible_cells = page.evaluate('''
                () => {
                    const cells = document.querySelectorAll('[data-cell-id], [role="gridcell"], td, th');
                    let texts = [];
                    cells.forEach(c => {
                        const rect = c.getBoundingClientRect();
                        if (rect.top >= 0 && rect.top <= window.innerHeight) {
                            const t = c.innerText?.trim();
                            if (t) texts.push(t);
                        }
                    });
                    return texts;
                }
            ''')
            if visible_cells:
                collected_cells.extend(visible_cells)

            # 向右滚动
            for _ in range(5):
                page.keyboard.press('ArrowRight')
            time.sleep(0.1)

        # 向下滚动
        for _ in range(10):
            visible_cells = page.evaluate('''
                () => {
                    const cells = document.querySelectorAll('[data-cell-id], [role="gridcell"], td, th');
                    let texts = [];
                    cells.forEach(c => {
                        const rect = c.getBoundingClientRect();
                        if (rect.top >= 0 && rect.top <= window.innerHeight) {
                            const t = c.innerText?.trim();
                            if (t) texts.push(t);
                        }
                    });
                    return texts;
                }
            ''')
            if visible_cells:
                collected_cells.extend(visible_cells)

            page.keyboard.press('PageDown')
            time.sleep(0.2)

        unique_cells = list(dict.fromkeys(collected_cells))
        if len(unique_cells) > 10:
            print(f"  滚动收集: {len(unique_cells)} 个单元格", file=__import__('sys').stderr)
            return '\n'.join(unique_cells)
    except Exception as e:
        print(f"  滚动收集失败: {e}", file=__import__('sys').stderr)
    return None


def _extract_table_container(page) -> str:
    """方法3: 获取整个表格容器的文本"""
    try:
        table_selectors = ['[role="grid"]', '.sheet-content', '.spreadsheet', '[class*="sheet"]']

        for selector in table_selectors:
            try:
                table = page.query_selector(selector)
                if table:
                    text = table.evaluate('el => el.innerText')
                    if text and len(text.strip()) > 50:
                        print(f"  容器提取: 从 {selector} 获取 {len(text)} 字符", file=__import__('sys').stderr)
                        return text.strip()
            except:
                continue
    except Exception as e:
        print(f"  容器提取失败: {e}", file=__import__('sys').stderr)
    return None