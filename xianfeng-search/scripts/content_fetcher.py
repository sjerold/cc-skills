#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容抓取模块 - 抓取飞书文档内容并保存为Markdown
"""

import os
import sys
import time
import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONTENT_WAIT_TIMEOUT


def fetch_document_content(page, doc_url: str, wait_time: int = CONTENT_WAIT_TIMEOUT) -> Dict:
    """
    抓取文档内容

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

        # 打开文档页面 - 使用 domcontentloaded 减少被中断的机会
        try:
            page.goto(doc_url, timeout=30000, wait_until="domcontentloaded")
        except Exception as nav_error:
            # 如果导航被中断，检查当前URL是否已跳转到其他文档
            current_url = page.url
            if '/docx/' in current_url or '/sheets/' in current_url:
                print(f"  导航被中断，当前URL: {current_url[:60]}...", file=sys.stderr)
                # 继续抓取当前页面的内容（可能是重定向后的文档）
            else:
                raise nav_error

        time.sleep(3)

        # 检测最终URL，判断是否发生了重定向
        final_url = page.url
        if final_url != doc_url and ('/docx/' in final_url or '/sheets/' in final_url):
            print(f"  发生重定向: {doc_url.split('/')[-1][:15]} -> {final_url.split('/')[-1][:15]}", file=sys.stderr)
            doc_url = final_url  # 更新URL以便正确判断文档类型

        # 等待内容加载
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass

        # 检测文档类型，表格使用专门的抓取器
        if '/sheets/' in doc_url.lower():
            print("  检测到表格文档，使用表格抓取模式", file=sys.stderr)
            from sheets_fetcher import fetch_sheets_content
            return fetch_sheets_content(page, doc_url, result)

        # 普通文档：滚动加载完整内容
        content = _scroll_and_extract(page, wait_time)

        # 检查是否需要登录
        if 'login' in page.url.lower() or 'passport' in page.url.lower():
            result['error'] = '需要重新登录'
            return result

        # 提取标题
        result['title'] = _extract_title(page)

        if content:
            result['content'] = content
            result['success'] = True
            result['length'] = len(content)
            print(f"抓取成功: {result['title'][:30]}... ({len(content)} 字符)", file=sys.stderr)
        else:
            result['error'] = '未能提取文档内容'
            print(f"抓取失败: 无法提取内容", file=sys.stderr)

    except Exception as e:
        result['error'] = str(e)
        print(f"抓取失败: {e}", file=sys.stderr)

    return result


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

    # 点击文档区域确保焦点
    try:
        page.click('[contenteditable="true"]', timeout=2000)
    except:
        pass

    collected_text = []
    last_length = 0
    scroll_count = 0

    for _ in range(50):  # 最多滚动50次
        # 收集当前可见内容
        visible = page.evaluate('''
            () => {
                const blocks = document.querySelectorAll('[data-block-id]');
                return Array.from(blocks)
                    .filter(b => {
                        const r = b.getBoundingClientRect();
                        return r.top >= 0 && r.top <= window.innerHeight;
                    })
                    .map(b => b.innerText?.trim())
                    .filter(t => t)
                    .join('\\n');
            }
        ''')
        if visible:
            collected_text.append(visible)

        # 滚动
        page.keyboard.press('PageDown')
        time.sleep(0.3)

        # 检查是否到底
        current_length = len(page.content())
        if current_length == last_length:
            time.sleep(0.5)
            if len(page.content()) == last_length:
                break
        last_length = current_length
        scroll_count += 1

    print(f"  滚动完成: {scroll_count} 次", file=sys.stderr)

    # 合并去重
    if collected_text:
        unique = list(dict.fromkeys(collected_text))
        merged = '\n\n'.join(unique)
        print(f"  收集到 {len(unique)} 段文本, 共 {len(merged)} 字符", file=sys.stderr)
        return merged

    # 备用：直接提取编辑器内容
    return _extract_editor_content(page)


def _extract_editor_content(page) -> str:
    """从编辑器提取内容 - 多种备用方案"""
    # 尝试多种选择器
    selectors = [
        '[contenteditable="true"]',
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

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(f"- **URL**: {doc_info['url']}\n")
            f.write(f"- **ID**: {doc_id}\n")
            f.write(f"- **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **内容长度**: {doc_info.get('length', 0)} 字符\n\n")
            f.write("---\n\n")
            f.write(doc_info['content'])

        print(f"已保存: {filepath}", file=sys.stderr)
        return filepath

    except Exception as e:
        print(f"保存失败: {e}", file=sys.stderr)
        return None


if __name__ == '__main__':
    print("内容抓取模块 - 请通过 xianfeng_search.py 调用")