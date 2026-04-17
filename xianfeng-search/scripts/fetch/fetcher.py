#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 文档抓取入口

统一入口，优先使用 API 方式获取完整内容，DOM 方式作为备用。
"""

import sys
import time
import os

# 使用绝对导入
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from core import CONTENT_WAIT_TIMEOUT, extract_doc_id
from .api_fetcher import fetch_via_api
from .dom_fetcher import scroll_and_extract, extract_title


def fetch_document_content(page, doc_url: str, wait_time: int = CONTENT_WAIT_TIMEOUT) -> dict:
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

        doc_id = extract_doc_id(doc_url)

        # 方式1: API方式获取内容
        api_content = fetch_via_api(page, doc_url, doc_id)
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

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass

        # 检测文档类型
        if '/sheets/' in doc_url.lower() or '/sheet/' in doc_url.lower():
            print("  检测到表格文档，使用表格抓取模式", file=sys.stderr)
            from .sheets_fetcher import fetch_sheets_content
            return fetch_sheets_content(page, doc_url, result)

        # 普通文档：滚动加载完整内容
        content = scroll_and_extract(page, wait_time)

        # 检查登录
        if 'login' in page.url.lower() or 'passport' in page.url.lower():
            result['error'] = '需要重新登录'
            return result

        # 提取标题
        result['title'] = extract_title(page)

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