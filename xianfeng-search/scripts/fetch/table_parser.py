#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 表格解析模块

负责从飞书API数据或DOM中提取表格内容并转换为Markdown格式。
"""

import sys
from typing import Dict, List


def extract_table_text_from_cell_set(cell_set: Dict, rows_id: List, columns_id: List, block_map: Dict, extract_block_text_fn) -> str:
    """
    提取表格内容 - cell_set格式

    Args:
        cell_set: 单元格数据映射
        rows_id: 行ID列表
        columns_id: 列ID列表
        block_map: 所有块的映射表
        extract_block_text_fn: 提取块文本的函数

    Returns:
        Markdown格式表格字符串
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
                cell_text = extract_block_text_fn(cell_block, block_map, depth=1)
                if cell_text and cell_text.strip():
                    cells.append(cell_text.strip())
                else:
                    cells.append('')
                    empty_cells += 1
            else:
                # 直接从 cell_data 提取文本
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

    # 如果大部分单元格是空的，返回空字符串（需要用DOM方式）
    if total_cells > 0 and empty_cells / total_cells > 0.8:
        return ''

    return build_markdown_table(table_rows)


def extract_table_text_from_children(children: List, block_map: Dict, extract_block_text_fn) -> str:
    """
    提取表格内容 - children格式

    Args:
        children: 子块ID列表
        block_map: 所有块的映射表
        extract_block_text_fn: 提取块文本的函数

    Returns:
        Markdown格式表格字符串
    """
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
                cell_text = extract_block_text_fn(cell_block, block_map, depth=1)
                row_cells.append(cell_text.strip() if cell_text else '')

            table_rows.append(row_cells)

    return build_markdown_table(table_rows)


def extract_table_text_from_cells(cells: List, block_map: Dict, extract_block_text_fn) -> str:
    """
    提取表格内容 - cells格式（私有化部署）

    Args:
        cells: 单元格信息列表
        block_map: 所有块的映射表
        extract_block_text_fn: 提取块文本的函数

    Returns:
        Markdown格式表格字符串
    """
    table_rows = []

    for row_cells in cells:
        row_data = []
        for cell_info in row_cells:
            if isinstance(cell_info, dict):
                block_id = cell_info.get('block_id', '')
                if block_id and block_id in block_map:
                    cell_block = block_map[block_id].get('data', {})
                    cell_text = extract_block_text_fn(cell_block, block_map, depth=1)
                    row_data.append(cell_text.strip() if cell_text else '')
                else:
                    text = cell_info.get('text', '')
                    row_data.append(str(text).strip() if text else '')
            else:
                row_data.append('')
        table_rows.append(row_data)

    return build_markdown_table(table_rows)


def build_markdown_table(table_rows: List[List[str]]) -> str:
    """
    将表格数据转换为Markdown格式

    Args:
        table_rows: 表格行数据列表

    Returns:
        Markdown格式表格字符串
    """
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


def extract_cell_text_from_children(block_data: Dict, block_map: Dict, extract_block_text_fn) -> str:
    """
    从table_cell类型的块中提取文本

    Args:
        block_data: 块数据
        block_map: 所有块的映射表
        extract_block_text_fn: 提取块文本的函数

    Returns:
        单元格文本内容
    """
    children = block_data.get('children', [])
    if not children:
        return ''

    text_parts = []
    for child_id in children:
        if child_id in block_map:
            child_block = block_map[child_id].get('data', {})
            child_text = extract_block_text_fn(child_block, block_map, 1)
            if child_text:
                text_parts.append(child_text)

    return ''.join(text_parts)