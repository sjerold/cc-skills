#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
点击式链接抓取 - 在新标签页中打开链接
"""

import sys
import os
import asyncio

_common_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'common', 'scripts')
sys.path.insert(0, _common_dir)

try:
    from chrome_manager import get_browser_async, get_page_async, close_browser_async, close_page_async, HAS_PLAYWRIGHT
except ImportError:
    from chrome_manager import get_browser_async, get_page_async, close_browser_async, close_page_async, HAS_PLAYWRIGHT

try:
    from content_parser import extract_content, check_anti_crawl
except ImportError:
    from content_parser import extract_content, check_anti_crawl

try:
    from markdown_writer import save_result_to_markdown
except ImportError:
    from markdown_writer import save_result_to_markdown


async def click_and_fetch_new_tab(browser, page, link_selector, timeout=30000, wait_after_click=15):
    """在页面上点击链接（在新标签页打开），等待跳转，然后抓取内容"""
    try:
        link_element = await page.query_selector(link_selector)
        if not link_element:
            return {'success': False, 'error': '链接元素不存在'}

        link_href = await link_element.get_attribute('href')
        link_text = await link_element.inner_text()

        print(f"点击链接: {link_text[:30]}...", file=sys.stderr)

        # 获取当前页面数
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        pages_before = len(context.pages)

        # 使用 Ctrl+Click 在新标签页打开
        await link_element.click(modifiers=['Control'])

        # 等待新标签页出现
        waited = 0
        new_page = None

        while waited < 5:
            await asyncio.sleep(1)
            waited += 1
            if len(context.pages) > pages_before:
                new_page = context.pages[-1]
                break

        if not new_page:
            # 尝试直接打开链接
            print("尝试直接打开链接...", file=sys.stderr)
            new_page = await context.new_page()
            await new_page.goto(link_href, timeout=timeout, wait_until="load")

        # 等待跳转完成
        waited = 0
        while waited < wait_after_click:
            await asyncio.sleep(1)
            waited += 1
            current_url = new_page.url
            if 'baidu.com/link' not in current_url and 'baidu.com/s' not in current_url:
                print(f"跳转成功({waited}s): {current_url[:60]}...", file=sys.stderr)
                break
            if waited % 3 == 0:
                print(f"等待跳转... {waited}s (当前: {current_url[:50]}...)", file=sys.stderr)

        try:
            await new_page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        final_url = new_page.url
        html = await new_page.content()

        if check_anti_crawl(html, final_url):
            await close_page_async(new_page)
            return {'success': False, 'url': final_url, 'original_url': link_href, 'anti_crawl': True, 'error': '遇到反爬限制'}

        content_data = extract_content(html, final_url)
        if content_data['length'] < 50:
            await close_page_async(new_page)
            return {'success': False, 'url': final_url, 'original_url': link_href, 'error': f'内容过短'}

        result = {
            'success': True, 'url': final_url, 'original_url': link_href,
            'title': content_data['title'], 'content': content_data['content'],
            'length': content_data['length'], 'link_text': link_text, 'fetch_type': 'click_new_tab'
        }

        await close_page_async(new_page)
        return result

    except Exception as e:
        return {'success': False, 'error': str(e)}


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description='点击式链接抓取')
    parser.add_argument('--test', action='store_true', help='测试模式')
    args = parser.parse_args()

    if args.test:
        async def test():
            search_url = 'https://www.baidu.com/s?wd=%E6%95%B0%E5%AD%97%E4%BA%BA%E6%B0%91%E5%B8%81&tn=news'
            playwright, browser = await get_browser_async()
            page = await get_page_async(browser, url=search_url)
            await page.wait_for_load_state("load")
            await asyncio.sleep(3)

            links = await page.query_selector_all('div.result h3 a')
            print(f"找到 {len(links)} 个链接", file=sys.stderr)

            if links:
                result = await click_and_fetch_new_tab(browser, page, 'div.result h3 a')
                with open('C:/Users/admin/Downloads/test_click_result.txt', 'w', encoding='utf-8') as f:
                    f.write(str(result))
                print('Result saved to test_click_result.txt')
                if result.get('success'):
                    print(f"URL: {result['url']}")
                    print(f"Title: {result['title']}")
                    print(f"Length: {result['length']}")

            await close_page_async(page)
            await close_browser_async(browser, playwright, keep_running=True)

        asyncio.run(test())
