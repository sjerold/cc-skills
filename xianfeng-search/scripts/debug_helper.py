#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试辅助模块 - 页面结构分析
"""

import sys
import json
from typing import Dict


def debug_page_structure(page) -> str:
    """
    调试页面结构 - 输出HTML分析选择器

    Args:
        page: Playwright页面对象

    Returns:
        页面结构摘要JSON
    """
    print("\n" + "=" * 60, file=sys.stderr)
    print("调试页面结构...", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    result = {
        'url': page.url,
        'title': page.title(),
        'file_list_html': '',
        'potential_items': [],
        'classes_found': [],
        'virtualized_list_info': '',
    }

    try:
        # 获取页面HTML
        body_html = page.evaluate('document.body.innerHTML')
        print(f"页面总长度: {len(body_html)} 字符", file=sys.stderr)

        # 检查虚拟化列表状态
        result['virtualized_list_info'] = _check_virtualized_list(page)

        # 查找文件列表容器
        result['file_list_html'] = _find_list_container(page)

        # 查找文件项元素
        result['potential_items'] = _find_potential_items(page)

        # 收集class名
        result['classes_found'] = _collect_classes(page)

    except Exception as e:
        print(f"调试失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60, file=sys.stderr)
    return json.dumps(result, ensure_ascii=False, indent=2)


def _check_virtualized_list(page) -> str:
    """检查虚拟化列表状态"""
    try:
        # 查找虚拟化列表容器
        virtualized_selectors = [
            '.explorer-file-list-virtualized',
            '[class*="virtualized"]',
            '[class*="VirtualList"]',
            '.file-list-container',
        ]

        for selector in virtualized_selectors:
            try:
                container = page.query_selector(selector)
                if container:
                    html = container.evaluate('el => el.outerHTML[:500]')
                    print(f"找到虚拟化列表容器: {selector}", file=sys.stderr)
                    return html
            except:
                continue

        # 检查placeholder（说明列表未渲染）
        placeholder = page.query_selector('[class*="placeholder"]')
        if placeholder:
            print("检测到placeholder，列表可能未渲染", file=sys.stderr)
            return placeholder.evaluate('el => el.className')

        return '未找到虚拟化列表'
    except:
        return '检查失败'


def _find_list_container(page) -> str:
    """查找文件列表容器"""
    selectors = [
        '.file-list', '.doc-list', '.drive-list', '.list-container',
        '[role="list"]', '.content-list', '.tree-list', '.virtual-list',
        '[class*="list"]', '[class*="List"]', '[class*="drive"]', '[class*="Drive"]',
    ]

    for selector in selectors:
        try:
            container = page.query_selector(selector)
            if container:
                html = container.evaluate('el => el.outerHTML')
                print(f"\n找到容器: {selector}, HTML长度: {len(html)}", file=sys.stderr)
                return html[:2000]
        except:
            continue

    return ''


def _find_potential_items(page) -> list:
    """查找可能的文件项元素"""
    patterns = [
        'div[class*="item"]', 'div[class*="row"]', 'div[class*="file"]',
        'div[class*="doc"]', 'div[data-id]', 'tr', 'li', '[role="listitem"]',
    ]

    items = []
    for pattern in patterns:
        try:
            elements = page.query_selector_all(pattern)
            if elements:
                print(f"\n模式 '{pattern}' 找到 {len(elements)} 个元素", file=sys.stderr)
                first_html = elements[0].evaluate('el => el.outerHTML')[:500]
                items.append({
                    'selector': pattern,
                    'count': len(elements),
                    'first_html': first_html
                })
        except:
            continue

    return items


def _collect_classes(page) -> list:
    """收集页面class名"""
    try:
        all_classes = page.evaluate('''
            Array.from(document.querySelectorAll('[class]'))
                .map(el => el.className)
                .filter(c => c && c.length > 0)
                .slice(0, 50)
        ''')

        print(f"\n发现的关键class (前30个):", file=sys.stderr)
        classes = []
        for cls in all_classes[:30]:
            if cls and len(str(cls)) < 100:
                print(f"  - {cls}", file=sys.stderr)
                classes.append(str(cls))
        return classes
    except:
        return []


if __name__ == '__main__':
    print("调试辅助模块 - 请通过 directory_scanner.py 调用")