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

# 确保当前目录在 sys.path 最前面，避免加载错误版本模块
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# 导入异步 chrome_manager
from chrome_manager import (
    get_browser_async, get_page_async, close_browser_async, close_page_async,
    HAS_PLAYWRIGHT
)

# 导入内容解析模块（确保加载本目录版本）
from content_parser import extract_content, check_anti_crawl, is_redirect_url

# 导入Markdown写入模块
from markdown_writer import save_result_to_markdown


# ============ 异步辅助方法 ============

async def wait_for_redirect(page, original_url, max_wait=10, check_interval=1):
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


async def _close_popups(page):
    """尝试关闭常见弹窗"""
    # 弹窗关闭按钮选择器（按优先级排序）
    popup_close_selectors = [
        # 知乎登录弹窗
        '.Modal-closeButton', 'button.Modal-close',
        '[aria-label="关闭"]',
        # 通用关闭按钮
        '.close', '.close-btn', '.modal-close', '.popup-close',
        'button[aria-label*="关闭"]', 'button[aria-label*="close"]',
        '.dialog-close', '.overlay-close',
        # Cookie 同意弹窗
        '.cookie-banner button', '[class*="accept"]', '[class*="consent"]',
    ]

    for selector in popup_close_selectors:
        try:
            elem = await page.query_selector(selector)
            if elem:
                is_visible = await elem.is_visible()
                if is_visible:
                    await elem.click(timeout=1000)
                    await asyncio.sleep(0.3)
                    print(f"已关闭弹窗: {selector}", file=sys.stderr)
                    break  # 只关闭一个弹窗
        except:
            pass

    # 按 ESC 键尝试关闭弹窗
    try:
        await page.keyboard.press('Escape')
        await asyncio.sleep(0.2)
    except:
        pass


# 跳过的域名（视频、图片、下载站等）
SKIP_DOMAINS = [
    'bilibili.com', 'youtube.com', 'youtu.be', 'youku.com',
    'iqiyi.com', 'v.qq.com', 'douyin.com', 'kuaishou.com',
    'acfun.cn', 'ted.com',
    'image.baidu.com', 'images.baidu.com', 'pixiv.net',
    'unsplash.com', 'pinterest.com', 'instagram.com',
    'download.csdn.net', 'pan.baidu.com', 'wenku.baidu.com',
]


def _should_skip_url(url):
    """检查URL是否应该跳过"""
    url_lower = url.lower()
    for domain in SKIP_DOMAINS:
        if domain in url_lower:
            return True
    return False


async def _fetch_with_page(page, url, timeout=30000, wait_time=3):
    """使用给定page抓取URL（内部方法）

    Args:
        page: Playwright Page对象
        url: 要抓取的URL
        timeout: 超时时间
        wait_time: 基础等待时间

    Returns:
        dict: 抓取结果
    """
    # 检查是否应该跳过
    if _should_skip_url(url):
        return {'success': False, 'url': url, 'original_url': url,
                'skipped': True, 'error': '视频/图片/下载网站，跳过抓取'}

    try:
        # 使用 domcontentloaded 而非 load，更快开始抓取
        await page.goto(url, timeout=timeout, wait_until="domcontentloaded")

        # 等待跳转完成（如果是跳转链接）
        await wait_for_redirect(page, url)

        # 获取最终 URL，判断是否需要特殊处理
        final_url = page.url

        # 尝试关闭常见弹窗
        await _close_popups(page)

        # 根据网站类型调整等待时间
        extra_wait = 2
        if 'zhihu.com' in final_url:
            extra_wait = 8  # 知乎需要更长等待
        elif 'csdn.net' in final_url or 'blog.csdn.net' in final_url:
            extra_wait = 5
        elif 'cnblogs.com' in final_url:
            extra_wait = 5

        await asyncio.sleep(extra_wait)

        # 使用 wait_for_selector 等待主要内容元素加载
        content_selectors = [
            'article', '.article-content', '.content', '.post-content',
            '.lemma-summary', '.para',  # 百度百科
            '.main-content', '#content', 'main',
            '.detail', '.body', '.text',
            # 知乎
            '.Post-RichText', '.RichText', '.RichContent', '.RichContent-inner',
            '[class*="RichText"]', '.Post-Main',
            # CSDN
            '#article_content', '.article-content', '.markdown_views',
            '#content_views', '.htmledit_views',
            # 博客园
            '.postBody', '.post-body', '#cnblogs_post_body',
            # 通用
            '.entry-content', '.post', '.article',
        ]

        content_loaded = False
        combined_selector = ', '.join(content_selectors)
        try:
            await page.wait_for_selector(combined_selector, timeout=10000)
            content_loaded = True
        except:
            pass

        # 如果没有匹配的内容元素，等待 networkidle
        if not content_loaded:
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass

        # 额外等待动态内容渲染（增加到 3 秒）
        await asyncio.sleep(3)

        final_url = page.url
        html = await page.content()

        if check_anti_crawl(html, final_url):
            print(f"  反爬检测: {final_url[:50]}", file=sys.stderr)
            return {'success': False, 'url': final_url, 'original_url': url,
                    'anti_crawl': True, 'error': '遇到反爬限制'}

        content_data = extract_content(html, final_url)

        # 检查内容长度（降低阈值，因为清理后内容可能较短）
        if content_data['length'] < 30:
            print(f"  内容过短({content_data['length']}字符): {final_url[:50]}", file=sys.stderr)
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

    # 预过滤：跳过视频/图片/下载网站
    filtered_urls = []
    skipped_results = []
    for url in urls:
        if _should_skip_url(url):
            skipped_results.append({'success': False, 'url': url, 'original_url': url,
                                     'skipped': True, 'error': '视频/图片/下载网站'})
        else:
            filtered_urls.append(url)

    if skipped_results:
        print(f"跳过 {len(skipped_results)} 个视频/图片/下载网站", file=sys.stderr)

    if not filtered_urls:
        return skipped_results

    print(f"并行抓取 {len(filtered_urls)} 个URL（{workers} 并发）", file=sys.stderr)

    playwright, browser = await get_browser_async()
    if not browser:
        failed_results = [{'success': False, 'url': url, 'original_url': url, 'error': '无法连接Chrome'} for url in filtered_urls]
        return skipped_results + failed_results

    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    semaphore = asyncio.Semaphore(workers)

    async def fetch_one(url, idx):
        """单个URL抓取（复用 _fetch_with_page）"""
        async with semaphore:
            page = None
            try:
                page = await context.new_page()
                page.set_default_timeout(timeout)

                print(f"抓取 [{idx+1}/{len(filtered_urls)}]: {url[:50]}...", file=sys.stderr)

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
    tasks = [fetch_one(url, i) for i, url in enumerate(filtered_urls)]
    results = await asyncio.gather(*tasks)

    # 不调用 browser.close() 和 playwright.stop()，避免 EPIPE
    await close_browser_async(browser, playwright, keep_running=True)

    return skipped_results + list(results)


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