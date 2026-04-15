#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 异步并行抓取

使用 asyncio 并行抓取多个文档，同一 browser context 下创建多个 page。
"""

import sys
import os
import asyncio

# 添加路径
scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

# 添加 common 模块路径
plugins_dir = os.path.dirname(scripts_dir)
common_path = os.path.join(plugins_dir, 'common', 'scripts')
if common_path not in sys.path:
    sys.path.insert(0, common_path)

from chrome_manager import get_browser_async, get_page_async, close_browser_async, close_page_async

from core import CONTENT_WAIT_TIMEOUT, extract_doc_id, CONTENT_DIR
from fetch.api_fetcher import fetch_via_api
from fetch.dom_fetcher import scroll_and_extract, extract_title
from fetch.markdown_writer import save_as_markdown


async def fetch_single_doc_async(page, doc_url: str, doc_info: dict) -> dict:
    """
    异步抓取单个文档 - 使用 API 拦截方式

    Args:
        page: Playwright异步page对象
        doc_url: 文档URL
        doc_info: 文档信息（包含name, folder_path, id等）

    Returns:
        抓取结果字典
    """
    result = {
        'url': doc_url,
        'name': doc_info.get('name', 'N/A'),
        'success': False,
    }

    doc_id = extract_doc_id(doc_url)

    # 捕获的 API 响应
    captured_responses = []

    async def on_response(response):
        url = response.url
        if 'client_vars' in url or ('block' in url.lower() and 'vars' in url.lower()):
            captured_responses.append(response)

    try:
        # 监听 API 响应
        page.on('response', on_response)

        # 导航到文档页面
        await page.goto(doc_url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # 滚动触发 API 调用
        for _ in range(10):
            for _ in range(5):
                await page.keyboard.press('PageDown')
                await asyncio.sleep(0.1)
            await asyncio.sleep(1)

        await page.keyboard.press('Control+Home')
        await asyncio.sleep(1)

        # 移除监听器
        page.remove_listener('response', on_response)

        # 处理 API 响应
        if captured_responses:
            merged_block_map = {}
            merged_block_sequence = []
            title = doc_info.get('name', '未命名文档')
            seen_block_ids = set()

            for response in captured_responses:
                try:
                    data = await response.json()
                    if data.get('code') != 0:
                        continue

                    doc_data = data.get('data', {})
                    block_map = doc_data.get('block_map', {})
                    block_sequence = doc_data.get('block_sequence', [])

                    for block_id, block in block_map.items():
                        if block_id not in seen_block_ids:
                            merged_block_map[block_id] = block
                            seen_block_ids.add(block_id)

                    for block_id in block_sequence:
                        if block_id not in merged_block_sequence:
                            merged_block_sequence.append(block_id)

                    meta = doc_data.get('meta_map', {}).get(doc_id, {})
                    if meta.get('title'):
                        title = meta['title']

                except:
                    continue

            if merged_block_map:
                # 从 block_map 提取内容
                from fetch.api_fetcher import extract_content_from_blocks
                content = extract_content_from_blocks(merged_block_map, merged_block_sequence)

                if content and len(content) > 50:
                    result['success'] = True
                    result['title'] = title
                    result['content'] = content
                    result['length'] = len(content)
                    result['method'] = 'api_async'
                    return result

        # API 方式失败，用 DOM 方式备用
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        # 提取内容
        try:
            editor = await page.query_selector('[contenteditable]')
            if editor:
                content = await editor.evaluate('el => el.innerText')
            else:
                content = await page.evaluate('document.body.innerText')

            title_elem = await page.query_selector('.doc-title, .document-title, .title, h1')
            if title_elem:
                title = await title_elem.inner_text()
            else:
                page_title = await page.title()
                import re
                title = re.sub(r'\s*[-|]\s*(飞书|Lark|Feishu).*$', '', page_title).strip()

            if content and len(content.strip()) > 50:
                result['success'] = True
                result['title'] = title or '未命名文档'
                result['content'] = content.strip()
                result['length'] = len(result['content'])
                result['method'] = 'dom_async'
            else:
                result['error'] = '内容过短或未能提取'
                result['title'] = title or '未命名文档'

        except Exception as e:
            result['error'] = str(e)

    except Exception as e:
        result['error'] = str(e)

    return result


async def fetch_docs_parallel_async(docs: list, domain: str, workers: int = 2) -> list:
    """
    异步并行抓取多个文档

    Args:
        docs: 文档列表，每个包含 url, name, folder_path, id
        domain: 飞书域名
        workers: 并发数（默认2）

    Returns:
        抓取结果列表
    """
    if not docs:
        return []

    print(f"并行抓取 {len(docs)} 个文档（{workers} 并发）", file=sys.stderr)

    # 获取浏览器
    playwright, browser = await get_browser_async()
    if not browser:
        print("无法连接Chrome", file=sys.stderr)
        return [{'success': False, 'error': '无法连接Chrome', 'name': d.get('name')} for d in docs]

    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    semaphore = asyncio.Semaphore(workers)

    results = []

    async def fetch_one(doc, idx):
        """单个文档抓取"""
        async with semaphore:
            page = None
            try:
                page = await context.new_page()
                page.set_default_timeout(30000)

                doc_url = doc.get('url')
                if not doc_url:
                    return {'success': False, 'error': '缺少URL', 'name': doc.get('name')}

                # 构建完整URL
                base_url = domain if domain.startswith('https://') else f"https://{domain}"
                if doc_url.startswith('/'):
                    doc_url = base_url + doc_url

                print(f"抓取 [{idx+1}/{len(docs)}]: {doc.get('name', 'N/A')[:30]}...", file=sys.stderr)

                result = await fetch_single_doc_async(page, doc_url, doc)

                # 如果成功，保存为Markdown
                if result.get('success') and result.get('content'):
                    folder_path = doc.get('folder_path', '')
                    doc_id = doc.get('id', '')
                    # 传递 edit_time 用于保存到文件头
                    result['edit_time'] = doc.get('edit_time')
                    filepath = save_as_markdown(result, CONTENT_DIR, folder_path, doc_id)
                    result['file'] = filepath
                    print(f"  ✓ 抓取成功: {result.get('length', 0)} 字符", file=sys.stderr)
                else:
                    print(f"  ✗ 抓取失败: {result.get('error', '未知错误')}", file=sys.stderr)

                return result

            except Exception as e:
                print(f"  ✗ 抓取异常: {e}", file=sys.stderr)
                return {'success': False, 'error': str(e), 'name': doc.get('name')}
            finally:
                if page:
                    await close_page_async(page)

    # 并行执行
    tasks = [fetch_one(doc, i) for i, doc in enumerate(docs)]
    results = await asyncio.gather(*tasks)

    # 断开连接（保持Chrome运行）
    await close_browser_async(browser, playwright, keep_running=True)

    return list(results)


def fetch_docs_parallel(docs: list, domain: str, workers: int = 2) -> list:
    """
    并行抓取多个文档（同步包装）

    Args:
        docs: 文档列表
        domain: 飞书域名
        workers: 并发数

    Returns:
        抓取结果列表
    """
    # 使用新 event loop 避免与同步 Playwright 冲突
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(fetch_docs_parallel_async(docs, domain, workers))
    finally:
        loop.close()