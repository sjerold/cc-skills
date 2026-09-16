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

    lines.extend(["", "## 抓取来源", ""])
    lines.append("")
    lines.append("> 正文全文见对应网页 md 文件；综合要点见「搜索总结」，深度分析见「AI分析」。")
    lines.append("")

    for i, r in enumerate(fetched, 1):
        if not r.get('success'):
            continue
        title = r.get('title', '无标题')
        url = r.get('url', '')
        content_len = r.get('length', 0)
        filepath = r.get('file', '')

        suffix = f"，本地 `{os.path.basename(filepath)}`)" if filepath else ")"
        lines.append(f"{i}. **{title}** — [{url}]({url})（{content_len} 字{suffix}")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return report_path


_NAV_NOISE_PATTERNS = [
    # 页面导航/面包屑
    r'^(目录|contents|navigation|menu|面包屑|当前位置|首页|breadcrumb|toc\b)',
    # 版权/发布信息
    r'版权(声明|所有)', r'cc\s*[0-9.]', r'创作共用', r'原文出处',
    r'本文为博主原创', r'转载(注明|自)', r'最近(更新|推荐|发布)', r'发布于',
    r'原创\b', r'收录于', r'喜欢[0-9]*人', r'人学习', r'人看过',
    # 单字/纯标点/纯数字等无信息行
    r'^[\s·.—–/\-*]{0,200}$',
    r'^[0-9]{1,4}$',
    # 索引页首行(如 "Index – N")
    r'^(index|索引|색인)[\s\-—–:]',
    # 页面动态提示
    r'最新推荐文章于', r'本文为博主原创文章',
]


def _is_index_nav_title(title):
    """判断标题是否为索引/导航页，其正文通常无实质内容"""
    if not title:
        return False
    t = title.strip()
    if re.match(r'^(索引|색인|目錄|目录)[\s\-—–:：]', t):
        return True
    if re.match(r'^(index|the\s+index)[\s\-—–:：]', t, re.IGNORECASE):
        return True
    if re.search(r'\b(genindex|full\s+index|module\s+index)\b', t, re.IGNORECASE):
        return True
    return False


def _trim(text, limit):
    """截断文本，超长加省略号"""
    text = text.strip()
    if not text:
        return ''
    if len(text) > limit:
        return text[:limit].rstrip() + '...'
    return text


def _extract_meaningful_paras(body, title=''):
    """从正文提取有信息量的段落，跳过导航/标题重复/版权/过短等噪音。

    返回按出现顺序整理的非空段落列表；无实质内容时返回空列表。
    """
    if not body:
        return []

    # 索引/导航页整体判定：标题特征即视为无实质内容
    if _is_index_nav_title(title):
        return []

    paras = [p.strip() for p in body.split('\n')]
    # 合并相邻的短行，避免把被换行切断的句子拆碎
    merged = []
    buf = ''
    for p in paras:
        if not p:
            if buf:
                merged.append(buf)
                buf = ''
            continue
        buf = f"{buf} {p}".strip() if buf else p
    if buf:
        merged.append(buf)

    title_norm = title.strip()
    meaningful = []
    for para in merged:
        if len(para) < 40:
            continue
        if title_norm and para == title_norm:
            continue
        if any(re.search(pat, para, re.IGNORECASE) for pat in _NAV_NOISE_PATTERNS):
            continue
        meaningful.append(para)
        if len(meaningful) >= 3:
            break

    return meaningful


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

    lines.extend(["", "## 内容要点", "", "---", ""])

    for i, (filename, content) in enumerate(md_contents.items(), 1):
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else filename

        lines.append(f"### 来源 {i}: {title}")
        lines.append("")

        content_match = re.search(r'## 正文内容\s*\n([\s\S]+)$', content)
        body = (content_match.group(1).strip() if content_match else content).strip()

        # 抽取该来源有信息量的代表性段落，跳过导航/标题重复/版权/过短等噪音
        meaningful_paras = _extract_meaningful_paras(body, title)
        if not meaningful_paras:
            lines.append("*（本页正文无实质内容，可能为索引/导航页）*")
        else:
            # 只列第一条代表性要点，避免与网页全文重复堆砌
            lines.append(_trim(meaningful_paras[0], 200))
        lines.append("")
        lines.extend(["---", ""])

    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return summary_path