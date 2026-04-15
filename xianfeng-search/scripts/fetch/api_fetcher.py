#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - API方式抓取

通过拦截飞书 client_vars API 获取完整文档内容。
"""

import sys
import time
import re
from typing import Dict, List, Optional

from .table_parser import (
    extract_table_text_from_cell_set,
    extract_table_text_from_children,
    extract_table_text_from_cells,
    build_markdown_table,
)


def fetch_via_api(page, doc_url: str, doc_id: str) -> Optional[Dict]:
    """
    通过拦截 API 获取文档内容

    Args:
        page: Playwright页面对象
        doc_url: 文档URL
        doc_id: 文档ID

    Returns:
        包含title和content的字典，失败返回None
    """
    if not doc_id:
        return None

    # 获取浏览器上下文，创建新页面
    try:
        context = page.context
        api_page = context.new_page()
        print(f"  [API] 创建新页面进行抓取", file=sys.stderr)
    except Exception as e:
        print(f"  [API] 无法创建新页面: {e}", file=sys.stderr)
        return None

    try:
        # 存储捕获的响应
        captured_responses = []

        def on_response(response):
            url = response.url
            if 'client_vars' in url or ('block' in url.lower() and 'vars' in url.lower()):
                captured_responses.append(response)
                print(f"  [API] 捕获到响应 (共{len(captured_responses)}个): {url[:80]}...", file=sys.stderr)

        api_page.on('response', on_response)

        # 导航到文档页面
        print(f"  [API] 导航到文档...", file=sys.stderr)
        try:
            api_page.goto(doc_url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"  [API] 导航警告: {e}", file=sys.stderr)

        time.sleep(3)

        # 滚动加载完整内容，触发多个 API 调用
        print(f"  [API] 滚动加载完整内容...", file=sys.stderr)
        last_response_count = 0
        no_new_response_count = 0

        for scroll_round in range(10):
            for _ in range(20):
                api_page.keyboard.press('PageDown')
                time.sleep(0.1)

            time.sleep(2)

            current_count = len(captured_responses)
            if current_count > last_response_count:
                print(f"  [API] 第{scroll_round+1}轮: 新增 {current_count - last_response_count} 个响应", file=sys.stderr)
                last_response_count = current_count
                no_new_response_count = 0
            else:
                no_new_response_count += 1
                if no_new_response_count >= 2:
                    print(f"  [API] 无新响应，停止滚动", file=sys.stderr)
                    break

        api_page.keyboard.press('Control+Home')
        time.sleep(2)

        if not captured_responses:
            print(f"  [API] 超时，未收到响应", file=sys.stderr)
            return None

        print(f"  [API] 共收集 {len(captured_responses)} 个响应", file=sys.stderr)

        # 合并所有响应的 block_map
        merged_block_map = {}
        merged_block_sequence = []
        title = '未命名文档'
        seen_block_ids = set()

        for response in captured_responses:
            try:
                data = response.json()
                if data.get('code') != 0:
                    continue

                doc_data = data.get('data', {})
                block_map = doc_data.get('block_map', {})
                block_sequence = doc_data.get('block_sequence', [])

                # 合并 block_map
                for block_id, block in block_map.items():
                    if block_id not in seen_block_ids:
                        merged_block_map[block_id] = block
                        seen_block_ids.add(block_id)

                # 合并 block_sequence
                for block_id in block_sequence:
                    if block_id not in merged_block_sequence:
                        merged_block_sequence.append(block_id)

                # 提取标题
                meta = doc_data.get('meta_map', {}).get(doc_id, {})
                if meta.get('title'):
                    title = meta['title']

            except Exception as e:
                print(f"  [API] 解析响应失败: {e}", file=sys.stderr)
                continue

        print(f"  [API] 合并后: {len(merged_block_map)} 个块, {len(merged_block_sequence)} 个序列", file=sys.stderr)

        if not merged_block_map:
            print(f"  [API] 没有有效的响应数据", file=sys.stderr)
            return None

        # 提取内容
        content = extract_content_from_blocks(merged_block_map, merged_block_sequence)

        # 检查表格是否需要 DOM 补充
        table_blocks = [bid for bid, b in merged_block_map.items()
                        if b.get('data', {}).get('type') == 'table']
        content_has_tables = '| --- |' in content

        if table_blocks and not content_has_tables:
            print(f"  [API] 检测到 {len(table_blocks)} 个表格块但内容为空，尝试 DOM 补充...", file=sys.stderr)
            from .dom_fetcher import extract_all_tables_by_scrolling
            dom_tables = extract_all_tables_by_scrolling(api_page, merged_block_map)
            if dom_tables:
                for table_md in dom_tables:
                    content += f'\n\n{table_md}'

        print(f"  [API] 提取完成: {len(content)} 字符", file=sys.stderr)

        return {
            'title': title,
            'content': content,
        }

    except Exception as e:
        print(f"  [API] 处理异常: {e}", file=sys.stderr)
        return None

    finally:
        try:
            api_page.remove_listener('response', on_response)
            if api_page != page:
                api_page.close()
                print(f"  [API] 关闭临时页面", file=sys.stderr)
        except:
            pass


def extract_content_from_blocks(block_map: Dict, block_sequence: List) -> str:
    """
    从 block_map 和 block_sequence 提取文档内容

    Args:
        block_map: 所有块的映射表
        block_sequence: 主文档块顺序列表

    Returns:
        Markdown 格式的文档内容
    """
    content_parts = []
    processed_blocks = set()

    def process_block(block_id, indent_level=0):
        """递归处理块及其子块"""
        if block_id in processed_blocks:
            return
        processed_blocks.add(block_id)

        block = block_map.get(block_id, {})
        block_data = block.get('data', {})
        block_type = block_data.get('type', '')

        # 跳过表格相关类型
        if block_type in ['table_cell', 'table_row']:
            return

        # 检查 parent_id 是否是表格块
        parent_id = block_data.get('parent_id', '')
        if parent_id and parent_id in block_map:
            parent_block = block_map.get(parent_id, {})
            parent_type = parent_block.get('data', {}).get('type', '')
            if parent_type in ['table', 'table_cell', 'table_row']:
                return
            # 检查祖父块
            grandparent_id = parent_block.get('data', {}).get('parent_id', '')
            if grandparent_id and grandparent_id in block_map:
                grandparent_block = block_map.get(grandparent_id, {})
                grandparent_type = grandparent_block.get('data', {}).get('type', '')
                if grandparent_type in ['table', 'table_cell', 'table_row']:
                    return

        # 备用检测：遍历表格块检查是否是其子块
        is_table_child = False
        for potential_table_id, potential_block in block_map.items():
            if potential_block.get('data', {}).get('type') == 'table':
                table_data = potential_block.get('data', {})
                if block_id in table_data.get('children', []):
                    is_table_child = True
                    break
                cell_set = table_data.get('cell_set', {})
                if cell_set:
                    for cell_data in cell_set.values():
                        if isinstance(cell_data, dict) and cell_data.get('block_id') == block_id:
                            is_table_child = True
                            break
                cells = table_data.get('cells', [])
                if cells and isinstance(cells, list):
                    for row in cells:
                        if isinstance(row, list) and block_id in row:
                            is_table_child = True
                            break

        if is_table_child:
            return

        # 提取当前块的文本
        text = extract_block_text(block_data, block_map)

        if text and text.strip():
            # 根据类型格式化
            if block_type == 'heading1':
                content_parts.append(f'# {text}')
            elif block_type == 'heading2':
                content_parts.append(f'## {text}')
            elif block_type == 'heading3':
                content_parts.append(f'### {text}')
            elif block_type == 'heading4':
                content_parts.append(f'#### {text}')
            elif block_type == 'heading5':
                content_parts.append(f'##### {text}')
            elif block_type == 'heading6':
                content_parts.append(f'###### {text}')
            elif block_type == 'table':
                content_parts.append(text)
                return  # 表格块不处理子块
            elif block_type == 'bullet':
                content_parts.append(f'- {text}')
            elif block_type == 'ordered_list':
                content_parts.append(f'1. {text}')
            elif block_type == 'quote':
                content_parts.append(f'> {text}')
            elif block_type == 'code':
                content_parts.append(f'```\n{text}\n```')
            else:
                content_parts.append(text)

        # 处理子块
        children = block_data.get('children', [])
        for child_id in children:
            if child_id in block_map:
                process_block(child_id, indent_level + 1)

    # 按顺序处理主文档块
    for block_id in block_sequence:
        process_block(block_id)

    return '\n\n'.join(content_parts)


def extract_block_text(block_data: Dict, block_map: Dict, depth: int = 0) -> str:
    """
    从块数据中提取文本内容

    Args:
        block_data: 块数据字典
        block_map: 所有块的映射表
        depth: 递归深度（防止无限递归）
    """
    if depth > 5:
        return ''

    block_type = block_data.get('type', '')

    # table_cell 类型 - 从 children 获取内容
    if block_type == 'table_cell':
        children = block_data.get('children', [])
        if children:
            text_parts = []
            for child_id in children:
                if child_id in block_map:
                    child_block = block_map[child_id].get('data', {})
                    child_text = extract_block_text(child_block, block_map, depth + 1)
                    if child_text:
                        text_parts.append(child_text)
            return ''.join(text_parts)

    # 直接文本格式
    text_data = block_data.get('text', {})
    if text_data:
        # 格式1: initialAttributedTexts.text
        initial_text = text_data.get('initialAttributedTexts', {}).get('text', {})
        if initial_text:
            text_parts = []
            for key in sorted(initial_text.keys()):
                text = initial_text[key]
                if isinstance(text, str):
                    text_parts.append(text)
            result = ''.join(text_parts)
            if result.strip():
                return result

        # 格式2: segments
        segments = text_data.get('segments', [])
        if segments:
            text_parts = []
            for seg in segments:
                if isinstance(seg, dict):
                    text = seg.get('text', '')
                    if text:
                        text_parts.append(text)
                elif isinstance(seg, str):
                    text_parts.append(seg)
            result = ''.join(text_parts)
            if result.strip():
                return result

        # 格式3: 直接 text 字符串
        direct_text = text_data.get('text', '')
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text

    # 表格格式
    cell_set = block_data.get('cell_set', {})
    rows_id = block_data.get('rows_id', [])
    columns_id = block_data.get('columns_id', [])

    if cell_set and rows_id and columns_id:
        return extract_table_text_from_cell_set(cell_set, rows_id, columns_id, block_map,
                                                  lambda b, m, depth=0: extract_block_text(b, m, depth))

    children = block_data.get('children', [])
    if children and block_type == 'table':
        return extract_table_text_from_children(children, block_map,
                                                  lambda b, m, depth=0: extract_block_text(b, m, depth))

    cells = block_data.get('cells', [])
    if cells and block_type == 'table':
        return extract_table_text_from_cells(cells, block_map,
                                               lambda b, m, depth=0: extract_block_text(b, m, depth))

    return ''