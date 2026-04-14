#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容抓取模块 - 抓取飞书文档内容并保存为Markdown

支持两种方式：
1. API方式：拦截 client_vars API 响应获取完整文档内容
2. DOM方式：从页面元素提取内容（备用）
"""

import os
import sys
import time
import re
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONTENT_WAIT_TIMEOUT


def fetch_document_content(page, doc_url: str, wait_time: int = CONTENT_WAIT_TIMEOUT) -> Dict:
    """
    抓取文档内容

    优先使用 API 方式获取完整内容，DOM 方式作为备用

    Args:
        page: Playwright页面对象
        doc_url: 文档URL
        wait_time: 等待内容加载的时间（秒）

    Returns:
        包含文档信息的字典
    """
    result = {
        'url': doc_url,
        'success': False,
        'title': '',
        'content': '',
        'error': None
    }

    try:
        print(f"正在抓取: {doc_url[:60]}...", file=sys.stderr)

        # 提取文档ID
        doc_id = _extract_doc_id(doc_url)

        # 方式1: 使用 API 获取内容
        api_content = _fetch_via_api(page, doc_url, doc_id)
        if api_content:
            result['title'] = api_content['title']
            result['content'] = api_content['content']
            result['success'] = True
            result['length'] = len(result['content'])
            result['method'] = 'api'
            print(f"抓取成功(API): {result['title'][:30]}... ({len(result['content'])} 字符)", file=sys.stderr)
            return result

        # 方式2: DOM方式（备用）
        print("API方式失败，尝试DOM方式...", file=sys.stderr)

        # 打开文档页面
        try:
            page.goto(doc_url, timeout=30000, wait_until="domcontentloaded")
        except Exception as nav_error:
            current_url = page.url
            if '/docx/' in current_url or '/sheets/' in current_url:
                print(f"  导航被中断，当前URL: {current_url[:60]}...", file=sys.stderr)
            else:
                raise nav_error

        time.sleep(3)

        # 检测重定向
        final_url = page.url
        if final_url != doc_url and ('/docx/' in final_url or '/sheets/' in final_url):
            print(f"  发生重定向: {doc_url.split('/')[-1][:15]} -> {final_url.split('/')[-1][:15]}", file=sys.stderr)
            doc_url = final_url

        # 等待内容加载
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass

        # 检测文档类型
        if '/sheets/' in doc_url.lower():
            print("  检测到表格文档，使用表格抓取模式", file=sys.stderr)
            return _fetch_sheets_content(page, doc_url, result)

        # 普通文档：滚动加载完整内容
        content = _scroll_and_extract(page, wait_time)

        # 检查登录
        if 'login' in page.url.lower() or 'passport' in page.url.lower():
            result['error'] = '需要重新登录'
            return result

        # 提取标题
        result['title'] = _extract_title(page)

        if content:
            result['content'] = content
            result['success'] = True
            result['length'] = len(content)
            result['method'] = 'dom'
            print(f"抓取成功(DOM): {result['title'][:30]}... ({len(content)} 字符)", file=sys.stderr)
        else:
            result['error'] = '未能提取文档内容'

    except Exception as e:
        result['error'] = str(e)
        print(f"抓取失败: {e}", file=sys.stderr)

    return result


def _extract_doc_id(url: str) -> str:
    """从URL提取文档ID"""
    match = re.search(r'/docx/([^/?]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'/sheets/([^/?]+)', url)
    if match:
        return match.group(1)
    return ''


def _fetch_via_api(page, doc_url: str, doc_id: str) -> Optional[Dict]:
    """
    通过拦截 API 获取文档内容

    飞书文档内容通过 client_vars API 返回，包含完整的 block_map

    改进:
    1. 先滚动加载完整内容，再收集 API 响应
    2. 合并多个 API 响应的 block_map
    3. 处理完整的 block_sequence，包括嵌套结构
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
        # 存储捕获的响应 - 在滚动期间持续收集
        captured_responses = []

        def on_response(response):
            url = response.url
            # 捕获多种可能的 API 响应
            # 改进：不再精确匹配 doc_id（因为飞书可能使用不同的 token 格式）
            # 只匹配 client_vars 或 block_vars 相关 API
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

        # 等待初始加载
        time.sleep(3)

        # 关键：先滚动加载完整内容，触发多个 API 调用
        print(f"  [API] 滚动加载完整内容...", file=sys.stderr)
        last_response_count = 0
        no_new_response_count = 0

        for scroll_round in range(10):  # 最多滚动10轮
            # 滚动到底部
            for _ in range(20):
                api_page.keyboard.press('PageDown')
                time.sleep(0.1)

            time.sleep(2)  # 等待新内容加载

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

        # 滚回顶部，可能触发更多加载
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

                # 合并 block_sequence (保持顺序，去重)
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

        # 使用合并后的数据
        block_map = merged_block_map
        block_sequence = merged_block_sequence

        # 提取内容 - 改进的提取逻辑
        content_parts = []

        # 首先按 sequence 处理（保持文档结构）
        processed_blocks = set()

        def process_block(block_id, indent_level=0):
            """递归处理块及其子块"""
            if block_id in processed_blocks:
                return
            processed_blocks.add(block_id)

            block = block_map.get(block_id, {})
            block_data = block.get('data', {})
            block_type = block_data.get('type', '')

            # 跳过表格相关类型（它们由表格块统一处理）
            if block_type in ['table_cell', 'table_row']:
                return

            # 检查这个块的 parent_id 是否是表格块或表格相关块
            # 这防止表格单元格内的 text 块被单独处理（避免内容重复）
            parent_id = block_data.get('parent_id', '')
            if parent_id and parent_id in block_map:
                parent_block = block_map.get(parent_id, {})
                parent_type = parent_block.get('data', {}).get('type', '')
                if parent_type in ['table', 'table_cell', 'table_row']:
                    return
                # 也检查祖父块（表格单元格的子块）
                grandparent_id = parent_block.get('data', {}).get('parent_id', '')
                if grandparent_id and grandparent_id in block_map:
                    grandparent_block = block_map.get(grandparent_id, {})
                    grandparent_type = grandparent_block.get('data', {}).get('type', '')
                    if grandparent_type in ['table', 'table_cell', 'table_row']:
                        return

            # 备用检测：检查这个块是否属于某个表格块的子块（通过遍历表格块）
            # 适用于 parent_id 缺失的情况
            is_table_child = False
            for potential_table_id, potential_block in block_map.items():
                if potential_block.get('data', {}).get('type') == 'table':
                    table_data = potential_block.get('data', {})
                    # 检查 children (V2格式)
                    if block_id in table_data.get('children', []):
                        is_table_child = True
                        break
                    # 检查 cell_set (V1格式)
                    cell_set = table_data.get('cell_set', {})
                    if cell_set:
                        for cell_data in cell_set.values():
                            if isinstance(cell_data, dict) and cell_data.get('block_id') == block_id:
                                is_table_child = True
                                break
                    # 检查 cells (V3格式)
                    cells = table_data.get('cells', [])
                    if cells and isinstance(cells, list):
                        for row in cells:
                            if isinstance(row, list) and block_id in row:
                                is_table_child = True
                                break

            if is_table_child:
                return

            # 提取当前块的文本
            text = _extract_block_text(block_data, block_map)

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
                    # 表格块不要处理子块（单元格），否则会重复添加单元格内容
                    return
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

        # 处理未被 sequence 包含的块（可能是遗漏的内容）
        # 注意：飞书文档的所有内容都应该在 sequence 中按顺序处理
        # 处理未被 sequence 包含的块会导致表格单元格内容重复
        # 因此，不再处理未被 sequence 包含的块
        # for block_id, block in block_map.items():
        #     if block_id not in processed_blocks:
        #         block_data = block.get('data', {})
        #         block_type = block_data.get('type', '')
        #         # 排除表格相关类型
        #         if block_type in ['page', 'text', 'heading1', 'heading2', 'heading3',
        #                           'heading4', 'heading5', 'heading6', 'bullet',
        #                           'ordered_list', 'quote', 'code']:
        #             process_block(block_id)

        # 检查是否有未被处理的块（调试信息）
        unprocessed_count = len(block_map) - len(processed_blocks)
        if unprocessed_count > 0:
            print(f"  [API] 未处理块数量: {unprocessed_count} (可能是表格子块或已删除块)", file=sys.stderr)

        content = '\n\n'.join(content_parts)

        # 检查是否有表格块但内容中没有表格
        # 如果有表格块但内容中没有表格，用 DOM 方式补充
        table_blocks = [bid for bid, b in block_map.items() if b.get('data', {}).get('type') == 'table']
        content_has_tables = '| --- |' in content

        print(f"  [API] 表格块数量: {len(table_blocks)}, 内容包含表格: {content_has_tables}", file=sys.stderr)

        if table_blocks and not content_has_tables:
            print(f"  [API] 检测到 {len(table_blocks)} 个表格块但内容为空，尝试 DOM 滚动提取...", file=sys.stderr)

            # 使用滚动方式逐个提取表格
            dom_tables = _extract_all_tables_by_scrolling(api_page, block_map)

            if dom_tables:
                print(f"  [API] DOM 成功提取 {len(dom_tables)} 个表格", file=sys.stderr)
                for table_md in dom_tables:
                    content += f'\n\n{table_md}'
            else:
                print(f"  [API] DOM 表格提取失败", file=sys.stderr)
        elif table_blocks and content_has_tables:
            print(f"  [API] 表格已通过API提取，跳过DOM补充", file=sys.stderr)

        print(f"  [API] 提取完成: {len(content)} 字符，处理了 {len(processed_blocks)} 个块", file=sys.stderr)

        return {
            'title': title,
            'content': content,
            'block_count': len(processed_blocks)
        }

    except Exception as e:
        print(f"  [API] 处理异常: {e}", file=sys.stderr)
        return None

    finally:
        # 移除监听器并关闭新创建的页面
        try:
            api_page.remove_listener('response', on_response)
            if api_page != page:
                api_page.close()
                print(f"  [API] 关闭临时页面", file=sys.stderr)
        except:
            pass


def _extract_block_text(block_data: Dict, block_map: Dict, depth: int = 0) -> str:
    """从块数据中提取文本内容

    Args:
        block_data: 块数据字典
        block_map: 所有块的映射表
        depth: 递归深度（防止无限递归）
    """
    if depth > 5:  # 防止无限递归
        return ''

    block_type = block_data.get('type', '')

    # 方式0: table_cell 类型 - 需要从 children 中获取内容
    if block_type == 'table_cell':
        children = block_data.get('children', [])
        if children:
            text_parts = []
            for child_id in children:
                if child_id in block_map:
                    child_block = block_map[child_id].get('data', {})
                    child_text = _extract_block_text(child_block, block_map, depth + 1)
                    if child_text:
                        text_parts.append(child_text)
            return ''.join(text_parts)

    # 方式1: 直接文本 (飞书文档中最常见的格式)
    text_data = block_data.get('text', {})
    if text_data:
        # 尝试多种文本格式
        # 格式1: initialAttributedTexts.text
        initial_text = text_data.get('initialAttributedTexts', {}).get('text', {})
        if initial_text:
            # 合并所有文本片段
            text_parts = []
            for key in sorted(initial_text.keys()):
                text = initial_text[key]
                if isinstance(text, str):
                    text_parts.append(text)
            result = ''.join(text_parts)
            if result.strip():
                return result

        # 格式2: segments (飞书新版API格式)
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

    # 方式2: 表格 - 检查多种表格格式
    cell_set = block_data.get('cell_set', {})
    rows_id = block_data.get('rows_id', [])
    columns_id = block_data.get('columns_id', [])

    if cell_set and rows_id and columns_id:
        return _extract_table_text_v1(cell_set, rows_id, columns_id, block_map)

    # 方式3: 表格 - 新版格式 (children 方式)
    children = block_data.get('children', [])
    if children and block_data.get('type') == 'table':
        return _extract_table_text_v2(children, block_map)

    # 方式4: 表格 - cells 方式 (私有化部署格式)
    cells = block_data.get('cells', [])
    if cells and block_data.get('type') == 'table':
        return _extract_table_text_v3(cells, block_map)

    return ''


def _extract_table_text_v1(cell_set: Dict, rows_id: List, columns_id: List, block_map: Dict) -> str:
    """提取表格内容 - V1格式 (cell_set + rows_id + columns_id)

    注意：飞书 API 通常不返回单元格内容块，需要用 DOM 方式作为备用
    """
    table_rows = []
    empty_cells = 0
    total_cells = 0

    for row_id in rows_id:
        cells = []
        for col_id in columns_id:
            total_cells += 1
            # 尝试多种 cell_key 格式
            cell_key_options = [
                f"{row_id}{col_id}",
                f"{row_id}_{col_id}",
                f"{col_id}{row_id}",
                f"{col_id}_{row_id}",
            ]

            cell_data = None
            for cell_key in cell_key_options:
                if cell_key in cell_set:
                    cell_data = cell_set[cell_key]
                    break

            if not cell_data:
                cells.append('')
                empty_cells += 1
                continue

            block_id = cell_data.get('block_id', '')

            if block_id and block_id in block_map:
                cell_block = block_map[block_id].get('data', {})
                cell_text = _extract_block_text(cell_block, block_map, depth=1)
                if cell_text and cell_text.strip():
                    cells.append(cell_text.strip())
                else:
                    cells.append('')
                    empty_cells += 1
            else:
                # 尝试直接从 cell_data 提取文本
                cell_text = cell_data.get('text', '')
                if isinstance(cell_text, dict):
                    initial = cell_text.get('initialAttributedTexts', {}).get('text', {})
                    if initial:
                        cell_text = ''.join(initial.values())
                if cell_text and str(cell_text).strip():
                    cells.append(str(cell_text).strip())
                else:
                    cells.append('')
                    empty_cells += 1

        table_rows.append(cells)

    # 如果大部分单元格是空的，返回空字符串表示需要用 DOM 方式
    if total_cells > 0 and empty_cells / total_cells > 0.8:
        return ''

    return _build_markdown_table(table_rows)


def _extract_table_text_v2(children: List, block_map: Dict) -> str:
    """提取表格内容 - V2格式 (children 列表)"""
    table_rows = []

    for child_id in children:
        if child_id not in block_map:
            continue

        row_block = block_map[child_id].get('data', {})
        row_type = row_block.get('type', '')

        if row_type == 'table_row':
            row_cells = []
            row_children = row_block.get('children', [])

            for cell_id in row_children:
                if cell_id not in block_map:
                    continue

                cell_block = block_map[cell_id].get('data', {})
                cell_text = _extract_block_text(cell_block, block_map, depth=1)
                row_cells.append(cell_text.strip() if cell_text else '')

            table_rows.append(row_cells)

    return _build_markdown_table(table_rows)


def _extract_table_text_v3(cells: List, block_map: Dict) -> str:
    """提取表格内容 - V3格式 (cells 列表，私有化部署)"""
    table_rows = []

    for row_cells in cells:
        row_data = []
        for cell_info in row_cells:
            if isinstance(cell_info, dict):
                block_id = cell_info.get('block_id', '')
                if block_id and block_id in block_map:
                    cell_block = block_map[block_id].get('data', {})
                    cell_text = _extract_block_text(cell_block, block_map, depth=1)
                    row_data.append(cell_text.strip() if cell_text else '')
                else:
                    # 直接提取文本
                    text = cell_info.get('text', '')
                    row_data.append(str(text).strip() if text else '')
            else:
                row_data.append('')
        table_rows.append(row_data)

    return _build_markdown_table(table_rows)


def _build_markdown_table(table_rows: List[List[str]]) -> str:
    """将表格数据转换为 Markdown 格式"""
    if not table_rows:
        return ''

    # 过滤掉完全空的行
    non_empty_rows = [row for row in table_rows if any(cell.strip() for cell in row)]
    if not non_empty_rows:
        return ''

    md_lines = []

    # 表头
    header = '| ' + ' | '.join(non_empty_rows[0]) + ' |'
    md_lines.append(header)

    # 分隔线
    separator = '| ' + ' | '.join(['---'] * len(non_empty_rows[0])) + ' |'
    md_lines.append(separator)

    # 数据行
    for row in non_empty_rows[1:]:
        row_line = '| ' + ' | '.join(row) + ' |'
        md_lines.append(row_line)

    return '\n'.join(md_lines)


def _extract_tables_from_dom(page) -> Dict[str, str]:
    """
    使用 DOM 方式提取表格内容

    根据 Gemini 建议优化：
    1. 显式等待单元格内部文本节点出现
    2. 使用 inner_text() 而不是 text_content()
    3. 遍历时对每个 cell 调用 scroll_into_view_if_needed()
    4. 处理 Markdown 格式（换行转 <br>，转义 |）

    Returns:
        字典: {table_index: markdown_table_string}
    """
    try:
        # 飞书表格选择器 - 多种可能的容器
        table_selectors = [
            '.table-scrollable-content',  # 飞书表格容器
            'table.table',                 # 飞书 docx 表格
            'table',
        ]

        result = {}
        table_index = 0

        for selector in table_selectors:
            try:
                table_containers = page.locator(selector).all()
                print(f"  [DOM表格] 选择器 '{selector}' 找到 {len(table_containers)} 个元素", file=sys.stderr)
            except Exception as e:
                print(f"  [DOM表格] 选择器 '{selector}' 失败: {e}", file=sys.stderr)
                continue

            for idx, table_container in enumerate(table_containers):
                try:
                    # 1. 确保表格骨架可见
                    table_container.wait_for(state='visible', timeout=5000)

                    # 2. 关键：等待第一行单元格渲染完成
                    first_row = table_container.locator('tr').first
                    first_cell = first_row.locator('td, th').first

                    try:
                        first_cell.wait_for(state='visible', timeout=3000)
                    except Exception as e:
                        print(f"  [DOM表格] 表格 {idx} 第一单元格不可见: {e}", file=sys.stderr)
                        continue

                    # 3. 滚动表格到视图内，触发虚拟渲染
                    table_container.scroll_into_view_if_needed()
                    time.sleep(0.5)  # 给渲染引擎一点时间

                    # 4. 获取所有行
                    rows = table_container.locator('tr').all()
                    if not rows:
                        print(f"  [DOM表格] 表格 {idx} 没有行", file=sys.stderr)
                        continue

                    table_rows = []

                    for i, row in enumerate(rows):
                        cells = row.locator('td, th').all()
                        if not cells:
                            continue

                        row_data = []

                        for cell in cells:
                            # 5. 每个单元格滚动到视图内（打破虚拟 DOM 限制）
                            try:
                                cell.scroll_into_view_if_needed()
                            except:
                                pass

                            # 6. 使用 inner_text() 获取可见文本
                            try:
                                text = cell.inner_text().strip()
                                # 处理 Markdown 格式
                                text = text.replace('\n', '<br>').replace('|', '\\|')
                            except Exception as e:
                                text = ''

                            row_data.append(text)

                        if row_data and any(c for c in row_data):
                            table_rows.append(row_data)

                    print(f"  [DOM表格] 表格 {idx} 提取到 {len(table_rows)} 行", file=sys.stderr)

                    # 7. 有效表格才保留（至少2行，有内容）
                    if len(table_rows) >= 2 and any(c for row in table_rows for c in row):
                        md_table = _build_markdown_table(table_rows)
                        if md_table:
                            result[table_index] = md_table
                            table_index += 1
                            print(f"  [DOM表格] 表格 {idx} 转换 Markdown 成功", file=sys.stderr)

                except Exception as e:
                    print(f"  [DOM表格] 表格 {idx} 提取失败: {e}", file=sys.stderr)
                    continue

        print(f"  [DOM表格] 共提取 {len(result)} 个表格", file=sys.stderr)
        return result

    except Exception as e:
        print(f"  [DOM表格] 提取失败: {e}", file=sys.stderr)
        return {}


def _extract_all_tables_by_scrolling(page, block_map: Dict) -> List[str]:
    """
    通过滚动到每个表格位置来提取所有表格内容

    飞书使用虚拟渲染，只有可见区域的内容在 DOM 中。
    需要滚动到每个表格块的位置才能提取。

    Args:
        page: Playwright 页面对象
        block_map: API 返回的 block_map，用于定位表格块

    Returns:
        表格 Markdown 字符串列表
    """
    tables = []

    # 找到所有表格块的 ID
    table_block_ids = []
    for block_id, block in block_map.items():
        if block.get('data', {}).get('type') == 'table':
            table_block_ids.append(block_id)

    if not table_block_ids:
        return tables

    print(f"  [DOM表格] 找到 {len(table_block_ids)} 个表格块，逐个滚动提取...", file=sys.stderr)

    # 先检查页面上有哪些表格相关元素
    table_check = page.evaluate('''
        () => {
            const result = {
                tableScrollable: document.querySelectorAll('.table-scrollable-content').length,
                tableClass: document.querySelectorAll('table.table').length,
                tableTag: document.querySelectorAll('table').length,
                dataBlockId: document.querySelectorAll('[data-block-id]').length,
                docxTable: document.querySelectorAll('.docx-table').length,
            };
            // 找到所有可能的表格相关 class
            const allClasses = [];
            document.querySelectorAll('*').forEach(el => {
                if (el.className && typeof el.className === 'string') {
                    el.className.split(' ').forEach(c => {
                        if (c.includes('table') || c.includes('grid')) {
                            allClasses.push(c);
                        }
                    });
                }
            });
            result.tableRelatedClasses = [...new Set(allClasses)].slice(0, 20);
            return result;
        }
    ''')
    print(f"  [DOM表格] 页面表格元素: {table_check}", file=sys.stderr)

    for i, block_id in enumerate(table_block_ids):
        try:
            # 使用 JavaScript 滚动到表格位置
            found = page.evaluate(f'''
                () => {{
                    // 尝试通过多种方式定位表格
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

                    // 如果找不到，尝试在表格列表中按索引定位
                    const allTables = document.querySelectorAll('table.table, .table-scrollable-content');
                    if (allTables.length > {i}) {{
                        allTables[{i}].scrollIntoView({{ behavior: 'instant', block: 'center' }});
                        return {{ found: true, method: 'by_index' }};
                    }}

                    return {{ found: false, reason: 'no_table_element' }};
                }}
            ''')

            print(f"  [DOM表格] 表格 {i+1}: {found}", file=sys.stderr)

            if found and found.get('found'):
                time.sleep(1)  # 等待渲染

                # 提取当前可见的表格
                visible_tables = _extract_tables_from_dom(page)
                for idx, table_md in visible_tables.items():
                    if table_md not in tables:  # 避免重复
                        tables.append(table_md)
            else:
                print(f"  [DOM表格] 表格 {i+1} 未找到对应 DOM 元素", file=sys.stderr)

        except Exception as e:
            print(f"  [DOM表格] 表格 {i+1} 提取失败: {e}", file=sys.stderr)
            continue

    print(f"  [DOM表格] 滚动提取完成，共 {len(tables)} 个表格", file=sys.stderr)
    return tables


def _fetch_sheets_content(page, doc_url: str, result: Dict) -> Dict:
    """抓取飞书表格内容"""
    # 导入表格抓取模块
    from sheets_fetcher import fetch_sheets_content
    return fetch_sheets_content(page, doc_url, result)


def _scroll_and_extract(page, wait_time: int) -> str:
    """
    滚动页面加载内容并提取

    Args:
        page: Playwright页面对象
        wait_time: 等待时间

    Returns:
        提取的内容
    """
    print("正在滚动加载完整内容...", file=sys.stderr)

    # 等待编辑器加载（飞书使用 [contenteditable] 而非 [contenteditable="true"]）
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

    # 先滚动到底部，加载虚拟列表内容
    for _ in range(30):
        page.keyboard.press('PageDown')
        time.sleep(0.15)

    # 滚回顶部
    page.keyboard.press('Control+Home')
    time.sleep(1)

    # 方法1: 直接获取编辑器 innerText（最可靠）
    # 尝试多种编辑器选择器
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
    return _extract_editor_content(page)


def _extract_editor_content(page) -> str:
    """从编辑器提取内容 - 多种备用方案"""
    # 尝试多种选择器（飞书使用 [contenteditable] 而非 [contenteditable="true"]）
    selectors = [
        '[contenteditable]',
        '[contenteditable="true"]',
        '.editor',  # 私有部署版本
        '.editor-content',
        '.doc-content',
        '[class*="editor"]',
        '[class*="content-area"]',
        '.suite-editor',
        '[data-lark-record-format]',  # 飞书特定格式
    ]

    for selector in selectors:
        try:
            editor = page.query_selector(selector)
            if editor:
                text = editor.evaluate('el => el.textContent || el.innerText')
                if text and len(text.strip()) > 50:  # 降低阈值
                    return _clean_content(text.strip())
        except:
            continue

    # 最后尝试：提取整个页面的主要文本
    try:
        main_content = page.evaluate('''
            () => {
                // 尝试找到主内容区域
                const main = document.querySelector('main') || document.querySelector('[role="main"]') || document.body;
                // 提取所有段落文本
                const paragraphs = main.querySelectorAll('p, div[data-block-id], span[data-block-id], h1, h2, h3, li');
                return Array.from(paragraphs)
                    .map(p => p.textContent?.trim())
                    .filter(t => t && t.length > 10)
                    .join('\\n\\n');
            }
        ''')
        if main_content and len(main_content) > 100:
            return _clean_content(main_content)
    except:
        pass

    return ""


def _extract_title(page) -> str:
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


def _clean_content(content: str) -> str:
    """清理内容"""
    lines = [line.strip() for line in content.split('\n') if line.strip()]

    # 移除过短的行
    cleaned = [l for l in lines if len(l) > 3 or l.startswith(('-', '*', '•', '1.', '2.', '3.'))]

    content = '\n'.join(cleaned)

    # 截断过长内容
    if len(content) > 50000:
        content = content[:50000] + '\n\n... (内容已截断)'

    return content


def save_as_markdown(doc_info: Dict, base_dir: str, folder_path: str = '', doc_id: str = '') -> Optional[str]:
    """
    将文档内容保存为Markdown文件

    Args:
        doc_info: 文档信息字典
        base_dir: 保存基础目录
        folder_path: 文件夹路径（用于保持目录结构）
        doc_id: 文档ID（用于文件名）

    Returns:
        保存的文件路径，失败返回None
    """
    if not doc_info.get('success') or not doc_info.get('content'):
        return None

    try:
        # 构建保存路径（保持目录结构）
        safe_folder = re.sub(r'[\\/:*?"<>|]', '_', folder_path) if folder_path else ''
        save_dir = os.path.join(base_dir, safe_folder) if safe_folder else base_dir
        os.makedirs(save_dir, exist_ok=True)

        # 文件名：名称-ID.md
        title = doc_info.get('title', '未命名')
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
        short_id = doc_id[:8] if doc_id else hashlib.md5(doc_info['url'].encode()).hexdigest()[:8]
        filename = f"{safe_title}-{short_id}.md"
        filepath = os.path.join(save_dir, filename)

        # 处理表格格式
        content = _format_tables_in_content(doc_info['content'])

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(f"- **URL**: {doc_info['url']}\n")
            f.write(f"- **ID**: {doc_id}\n")
            f.write(f"- **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **内容长度**: {doc_info.get('length', 0)} 字符\n\n")
            f.write("---\n\n")
            f.write(content)

        print(f"已保存: {filepath}", file=sys.stderr)
        return filepath

    except Exception as e:
        print(f"保存失败: {e}", file=sys.stderr)
        return None


def _format_tables_in_content(content: str) -> str:
    """
    检测并格式化内容中的表格数据

    飞书文档中表格数据可能以以下形式出现：
    - 连续的制表符分隔的数据行
    - 空行分隔的数据块
    """
    lines = content.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # 检测是否是表格行（包含多个连续空格或制表符分隔的数据）
        if _is_table_row(line):
            # 收集连续的表格行
            table_rows = [line]
            j = i + 1
            while j < len(lines) and _is_table_row(lines[j]):
                table_rows.append(lines[j])
                j += 1

            # 如果有至少2行表格数据，转换为Markdown表格
            if len(table_rows) >= 2:
                md_table = _convert_to_markdown_table(table_rows)
                result.append(md_table)
                i = j
            else:
                result.append(line)
                i += 1
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


def _is_table_row(line: str) -> bool:
    """判断是否是表格行"""
    stripped = line.strip()
    if not stripped:
        return False

    # 检测制表符分隔
    if '\t' in line and line.count('\t') >= 2:
        return True

    # 检测多个连续空格（至少3个连续空格，出现2次以上）
    spaces = re.findall(r' {3,}', line)
    if len(spaces) >= 2:
        return True

    return False


def _convert_to_markdown_table(rows: List[str]) -> str:
    """将数据行转换为Markdown表格"""
    md_rows = []

    for i, row in enumerate(rows):
        # 分割单元格（按制表符或多个空格）
        cells = re.split(r'\t| {3,}', row)
        cells = [c.strip() for c in cells if c.strip()]

        if not cells:
            continue

        md_row = '| ' + ' | '.join(cells) + ' |'
        md_rows.append(md_row)

        # 第一行后添加分隔线
        if i == 0:
            separator = '| ' + ' | '.join(['---'] * len(cells)) + ' |'
            md_rows.append(separator)

    return '\n'.join(md_rows)


if __name__ == '__main__':
    print("内容抓取模块 - 请通过 xianfeng_search.py 调用")