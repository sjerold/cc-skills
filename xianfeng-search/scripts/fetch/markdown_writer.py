#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - Markdown输出

将文档内容保存为Markdown文件。
"""

import os
import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional


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
        content = format_tables_in_content(doc_info['content'])

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(f"- **URL**: {doc_info['url']}\n")
            f.write(f"- **ID**: {doc_id}\n")
            # 保存 edit_time 用于增量缓存判断
            if doc_info.get('edit_time'):
                f.write(f"- **修改时间**: {doc_info['edit_time']}\n")
            f.write(f"- **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **内容长度**: {doc_info.get('length', 0)} 字符\n\n")
            f.write("---\n\n")
            f.write(content)

        print(f"已保存: {filepath}")
        return filepath

    except Exception as e:
        print(f"保存失败: {e}")
        return None


def format_tables_in_content(content: str) -> str:
    """
    检测并格式化内容中的表格数据
    """
    lines = content.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # 检测是否是表格行
        if is_table_row(line):
            # 收集连续的表格行
            table_rows = [line]
            j = i + 1
            while j < len(lines) and is_table_row(lines[j]):
                table_rows.append(lines[j])
                j += 1

            # 如果有至少2行表格数据，转换为Markdown表格
            if len(table_rows) >= 2:
                md_table = convert_to_markdown_table(table_rows)
                result.append(md_table)
                i = j
            else:
                result.append(line)
                i += 1
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


def is_table_row(line: str) -> bool:
    """判断是否是表格行"""
    stripped = line.strip()
    if not stripped:
        return False

    # 检测制表符分隔
    if '\t' in line and line.count('\t') >= 2:
        return True

    # 检测多个连续空格
    spaces = re.findall(r' {3,}', line)
    if len(spaces) >= 2:
        return True

    return False


def convert_to_markdown_table(rows: List[str]) -> str:
    """将数据行转换为Markdown表格"""
    md_rows = []

    for i, row in enumerate(rows):
        # 分割单元格
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