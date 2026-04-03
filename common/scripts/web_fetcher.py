#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页抓取模块 - 异步版本

使用异步 Playwright 抓取网页内容，复用用户Chrome的登录状态。

使用方式：
    from web_fetcher import fetch_url_async, fetch_urls_async

    result = await fetch_url_async('https://example.com')
    results = await fetch_urls_async(['url1', 'url2'], save_dir='./output')
"""

import sys
import os
import asyncio

# 导入异步 chrome_manager
try:
    from chrome_manager import (
        get_browser_async, get_page_async, close_browser_async, close_page_async,
        HAS_PLAYWRIGHT
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from chrome_manager import (
        get_browser_async, get_page_async, close_browser_async, close_page_async,
        HAS_PLAYWRIGHT
    )

# 导入内容解析模块
try:
    from content_parser import extract_content, check_anti_crawl, is_redirect_url
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from content_parser import extract_content, check_anti_crawl, is_redirect_url

# 导入Markdown写入模块
try:
    from markdown_writer import save_result_to_markdown
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from markdown_writer import save_result_to_markdown


# ============ 异步辅助方法 ============

async def wait_for_redirect(page, original_url, max_wait=5, check_interval=1):
    """等待页面跳转完成（循环检测）

    Args:
        page: Playwright Page对象
        original_url: 原始跳转链接URL
        max_wait: 最大等待时间（秒）
        check_interval: 检测间隔（秒）
    """
    # 基于原始URL判断是否是跳转链接
    if not is_redirect_url(original_url):
        return

    print(f"检测到跳转链接，等待跳转（最多{max_wait}秒）...", file=sys.stderr)
    waited = 0
    last_url = page.url

    while waited < max_wait:
        await asyncio.sleep(check_interval)
        waited += check_interval

        current_url = page.url

        # URL发生变化，说明跳转正在进行
        if current_url != last_url:
            # 如果跳转后的URL不再是重定向链接（允许是百度百科等百度旗下业务站），提前结束等待
            if not is_redirect_url(current_url):
                print(f"跳转成功({waited}s): {current_url[:60]}...", file=sys.stderr)
                try:
                    await page.wait_for_load_state("networkidle", timeout=2000)
                except:
                    pass
                return
            last_url = current_url

        if waited % 5 == 0:
            print(f"等待跳转... {waited}s", file=sys.stderr)

    # 超时后直接继续，抓取当前页面内容
    print(f"等待结束({max_wait}s): {page.url[:60]}...", file=sys.stderr)


async def _fetch_with_page(page, url, timeout=30000, wait_time=2):
    """使用给定page抓取URL（内部方法）

    Args:
        page: Playwright Page对象
        url: 要抓取的URL
        timeout: 超时时间
        wait_time: 基础等待时间

    Returns:
        dict: 抓取结果
    """
    try:
        await page.goto(url, timeout=timeout, wait_until="load")

        # 等待跳转完成（如果是跳转链接）
        await wait_for_redirect(page, url)

        # 使用 wait_for_selector 等待主要内容元素加载
        content_selectors = [
            'article', '.article-content', '.content', '.post-content',
            '.lemma-summary', '.para',  # 百度百科
            '.main-content', '#content', 'main',
            '.detail', '.body', '.text',
        ]

        content_loaded = False
        combined_selector = ', '.join(content_selectors)
        try:
            # 并行监控所有可能的内容选择器，只要有一处匹配就会立即返回，不会造成 N * 5s 的延迟
            await page.wait_for_selector(combined_selector, timeout=5000)
            content_loaded = True
            print(f"内容元素已加载完成", file=sys.stderr)
        except:
            pass

        # 如果没有匹配的内容元素，等待 networkidle
        if not content_loaded:
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass

        # 额外等待动态内容渲染
        await asyncio.sleep(wait_time)

        final_url = page.url
        html = await page.content()

        if check_anti_crawl(html, final_url):
            return {'success': False, 'url': final_url, 'original_url': url,
                    'anti_crawl': True, 'error': '遇到反爬限制'}

        content_data = extract_content(html, final_url)

        # 检查内容长度（降低阈值，因为清理后内容可能较短）
        if content_data['length'] < 50:
            return {'success': False, 'url': final_url, 'original_url': url,
                    'error': f'内容过短: {content_data["length"]} 字符'}

        return {
            'success': True, 'url': final_url, 'original_url': url,
            'title': content_data['title'], 'content': content_data['content'],
            'length': content_data['length'], 'fetch_type': 'playwright_async'
        }

    except Exception as e:
        return {'success': False, 'url': url, 'original_url': url, 'error': str(e)}


# ============ 公开API ============

async def fetch_url_async(url, timeout=30000, wait_time=2):
    """抓取单个URL（异步）

    Args:
        url: 要抓取的URL
        timeout: 超时时间（毫秒）
        wait_time: 等待时间（秒）

    Returns:
        dict: 抓取结果
    """
    playwright, browser = await get_browser_async()
    if not browser:
        return {'success': False, 'url': url, 'original_url': url, 'error': '无法连接Chrome'}

    page = None
    try:
        page = await get_page_async(browser, timeout=timeout)
        if not page:
            return {'success': False, 'url': url, 'original_url': url, 'error': '无法创建页面'}

        result = await _fetch_with_page(page, url, timeout, wait_time)
        return result

    finally:
        if page:
            await close_page_async(page)
        await close_browser_async(browser, playwright, keep_running=True)


async def fetch_urls_async(urls, save_dir=None, timeout=30000, workers=4):
    """并行抓取多个URL（异步）

    复用 _fetch_with_page 核心逻辑，共享 browser/context。

    Args:
        urls: URL列表
        save_dir: 保存目录
        timeout: 超时时间（毫秒）
        workers: 并发数

    Returns:
        list: 抓取结果列表
    """
    if not urls:
        return []

    print(f"并行抓取 {len(urls)} 个URL（{workers} 并发）", file=sys.stderr)

    playwright, browser = await get_browser_async()
    if not browser:
        return [{'success': False, 'url': url, 'original_url': url, 'error': '无法连接Chrome'} for url in urls]

    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    semaphore = asyncio.Semaphore(workers)

    async def fetch_one(url, idx):
        """单个URL抓取（复用 _fetch_with_page）"""
        async with semaphore:
            page = None
            try:
                page = await context.new_page()
                page.set_default_timeout(timeout)

                print(f"抓取 [{idx+1}/{len(urls)}]: {url[:50]}...", file=sys.stderr)

                result = await _fetch_with_page(page, url, timeout)

                if result.get('success') and save_dir:
                    save_result_to_markdown(result, save_dir)

                return result

            except Exception as e:
                print(f"抓取失败 [{idx+1}]: {e}", file=sys.stderr)
                return {'success': False, 'url': url, 'original_url': url, 'error': str(e)}
            finally:
                if page:
                    await close_page_async(page)

    # 并行执行
    tasks = [fetch_one(url, i) for i, url in enumerate(urls)]
    results = await asyncio.gather(*tasks)

    # 不调用 browser.close() 和 playwright.stop()，避免 EPIPE
    await close_browser_async(browser, playwright, keep_running=True)

    return list(results)


# ============ 同步包装（供命令行使用） ============

def fetch_url(url, timeout=30000, wait_time=2):
    """抓取单个URL（同步包装）"""
    return asyncio.run(fetch_url_async(url, timeout, wait_time))


def fetch_urls(urls, save_dir=None, timeout=30000, workers=4):
    """批量抓取URL（同步包装）"""
    return asyncio.run(fetch_urls_async(urls, save_dir, timeout, workers))


# ============ 命令行入口 ============

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='网页抓取工具（异步版本）')
    parser.add_argument('url', nargs='*', help='要抓取的URL')
    parser.add_argument('-o', '--output', help='保存目录')
    parser.add_argument('-w', '--workers', type=int, default=2, help='并发数')
    parser.add_argument('--test', action='store_true', help='测试抓取百度')

    args = parser.parse_args()

    if args.test:
        result = fetch_url('https://www.baidu.com')
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.url:
        urls = args.url
        results = fetch_urls(urls, save_dir=args.output, workers=args.workers)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    else:
        parser.print_help()