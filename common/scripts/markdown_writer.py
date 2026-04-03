#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown 文件生成模块

提供将抓取结果保存为 Markdown 文件的功能。
"""

import os
import re
import hashlib
from datetime import datetime


def sanitize_filename(name, max_length=50):
    """清理文件名，移除非法字符

    Args:
        name: 原始文件名
        max_length: 最大长度

    Returns:
        str: 安全的文件名
    """
    # 移除Windows非法字符
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
    # 截断长度
    return safe_name[:max_length]


def generate_hash(text, length=8):
    """生成文本的短哈希

    Args:
        text: 原始文本
        length: 哈希长度

    Returns:
        str: 短哈希字符串
    """
    return hashlib.md5(text.encode()).hexdigest()[:length]


def save_result_to_markdown(result, save_dir, filename=None):
    """将抓取结果保存为Markdown文件

    Args:
        result: 抓取结果字典
        save_dir: 保存目录
        filename: 可选的文件名（不含扩展名）

    Returns:
        str: 保存的文件路径，失败返回None
    """
    if not result.get('success') or not result.get('content'):
        return None

    os.makedirs(save_dir, exist_ok=True)

    # 生成文件名
    if not filename:
        title = result.get('title', 'untitled')
        safe_title = sanitize_filename(title)
        url_hash = generate_hash(result['original_url'])
        filename = f"{safe_title}_{url_hash}"

    filepath = os.path.join(save_dir, f"{filename}.md")

    # 写入内容
    content = format_result_as_markdown(result)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    result['file'] = filepath
    print(f"已保存: {filepath}", file=__import__('sys').stderr)
    return filepath


def format_result_as_markdown(result):
    """将抓取结果格式化为Markdown

    Args:
        result: 抓取结果字典

    Returns:
        str: Markdown格式的文本
    """
    title = result.get('title', '无标题')
    url = result.get('url', '')
    original_url = result.get('original_url', '')
    fetch_time = result.get('fetch_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    fetch_type = result.get('fetch_type', 'unknown')
    content = result.get('content', '')
    length = result.get('length', len(content))

    lines = [
        f"# {title}",
        "",
        f"- **URL**: {url}",
        f"- **原始URL**: {original_url}",
        f"- **抓取时间**: {fetch_time}",
        f"- **抓取方式**: {fetch_type}",
        f"- **内容长度**: {length} 字符",
        "",
        "---",
        "",
        "## 正文内容",
        "",
        content,
    ]

    return '\n'.join(lines)


def save_search_report(query, results, fetched, save_dir, session_id):
    """保存搜索报告

    Args:
        query: 搜索关键词
        results: 搜索结果列表
        fetched: 抓取结果列表
        save_dir: 保存目录
        session_id: 会话ID

    Returns:
        str: 报告文件路径
    """
    os.makedirs(save_dir, exist_ok=True)
    report_path = os.path.join(save_dir, f"搜索报告_{session_id}.md")

    lines = [
        f"# 搜索报告：{query}",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 会话ID：{session_id}",
        "",
        "## 搜索概况",
        "",
        f"- **搜索关键词**: {query}",
        f"- **搜索结果数**: {len(results)} 条",
        f"- **抓取成功数**: {sum(1 for r in fetched if r.get('success'))}/{len(fetched)} 条",
        "",
        "## 参考链接",
        "",
        "| 序号 | 标题 | URL | 质量分数 |",
        "|------|------|-----|----------|",
    ]

    for i, r in enumerate(results[:30], 1):
        title = r.get('title', 'N/A')[:40]
        url = r.get('url', '')
        score = r.get('score', 1.0)
        lines.append(f"| {i} | {title} | [链接]({url}) | {score:.2f} |")

    lines.extend(["", "## 抓取内容摘要", ""])

    for i, r in enumerate(fetched, 1):
        if r.get('success'):
            title = r.get('title', '无标题')
            url = r.get('url', '')
            content_len = r.get('length', 0)
            fetch_type = r.get('fetch_type', 'unknown')
            filepath = r.get('file', '')

            lines.extend([
                f"### {i}. {title}",
                "",
                f"- **URL**: {url}",
                f"- **内容长度**: {content_len} 字符",
                f"- **抓取方式**: {fetch_type}",
            ])

            if filepath:
                lines.append(f"- **本地文件**: `{os.path.basename(filepath)}`")

            lines.append("")

            content = r.get('content', '')
            if content:
                preview = content[:500]
                if len(content) > 500:
                    preview += '...'
                lines.extend([
                    "**内容预览**:",
                    "",
                    "```",
                    preview,
                    "```",
                    "",
                ])

            lines.append("---")
            lines.append("")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return report_path


def save_summary(query, results, md_contents, save_dir, session_id):
    """保存搜索总结

    Args:
        query: 搜索关键词
        results: 搜索结果列表
        md_contents: {filename: content} 字典
        save_dir: 保存目录
        session_id: 会话ID

    Returns:
        str: 总结文件路径
    """
    os.makedirs(save_dir, exist_ok=True)
    summary_path = os.path.join(save_dir, f"搜索总结_{session_id}.md")

    total_length = sum(len(content) for content in md_contents.values())

    lines = [
        f"# 搜索总结：{query}",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 会话ID：{session_id}",
        "",
        "## 统计信息",
        "",
        f"- **搜索结果**: {len(results)} 条",
        f"- **抓取文件**: {len(md_contents)} 个",
        f"- **总内容量**: {total_length:,} 字符",
        "",
        "## 参考来源",
        "",
    ]

    for i, (filename, content) in enumerate(md_contents.items(), 1):
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else filename
        lines.append(f"{i}. {title} (`{filename}`)")

    lines.extend(["", "## 整合内容", "", "---", ""])

    for i, (filename, content) in enumerate(md_contents.items(), 1):
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else filename

        lines.append(f"### 来源 {i}: {title}")
        lines.append("")

        content_match = re.search(r'## 正文内容\s*\n([\s\S]+)$', content)
        if content_match:
            body = content_match.group(1).strip()
            if len(body) > 3000:
                body = body[:3000] + '\n\n... (内容已截断)'
            lines.append(body)
        else:
            lines.append(content[:3000])

        lines.extend(["", "---", ""])

    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return summary_path