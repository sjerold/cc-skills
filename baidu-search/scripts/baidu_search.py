#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度搜索脚本 - 异步版本

使用异步 Playwright，配合 common 模块的异步 chrome_manager。
"""

import sys
import os
import json
import io
import argparse
import uuid
import urllib.parse
from datetime import datetime

# 添加common模块路径
_current_dir = os.path.dirname(os.path.abspath(__file__))
_common_dir = os.path.join(os.path.dirname(os.path.dirname(_current_dir)), 'common', 'scripts')
sys.path.insert(0, _common_dir)

# 确保 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 导入异步 common 模块
try:
    from chrome_manager import (
        get_browser_async, get_page_async, close_browser_async, close_page_async,
        HAS_PLAYWRIGHT
    )
except ImportError as e:
    print(f"无法导入chrome_manager: {e}", file=sys.stderr)
    HAS_PLAYWRIGHT = False

try:
    from web_fetcher import fetch_urls_async
except ImportError as e:
    print(f"无法导入web_fetcher: {e}", file=sys.stderr)

try:
    from content_parser import extract_content
except ImportError:
    sys.path.insert(0, _common_dir)
    from content_parser import extract_content

try:
    from markdown_writer import save_search_report, save_summary
except ImportError:
    sys.path.insert(0, _common_dir)
    from markdown_writer import save_search_report, save_summary

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# 导入评分器
try:
    from scorer import calculate_quality_score
except ImportError:
    _scorer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scorer.py')
    import importlib.util
    spec = importlib.util.spec_from_file_location("scorer", _scorer_path)
    scorer_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer_module)
    calculate_quality_score = scorer_module.calculate_quality_score


# ============ 配置 ============

DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser('~'), 'Downloads', 'baidu_search')


def generate_session_id():
    """生成会话ID"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    short_uuid = uuid.uuid4().hex[:8]
    return f"{timestamp}_{short_uuid}"


def get_session_dir(base_dir=None, session_id=None):
    """获取会话目录"""
    if base_dir is None:
        base_dir = DEFAULT_OUTPUT_DIR

    if session_id is None:
        session_id = generate_session_id()

    session_dir = os.path.join(base_dir, session_id)
    os.makedirs(session_dir, exist_ok=True)

    return session_dir, session_id


async def check_captcha_async(page):
    """检测验证码（异步）"""
    indicators = ['wappass.baidu.com', 'captcha', '验证']

    try:
        url = page.url.lower()
        content = await page.content()
        content_lower = content.lower()

        is_captcha = any(i in url for i in indicators) or '百度安全验证' in content

        if is_captcha:
            print("\n检测到验证码！", file=sys.stderr)
            return True
    except:
        pass
    return False


async def search_async(query, limit=50):
    """执行百度搜索（异步）

    Args:
        query: 搜索关键词
        limit: 结果数量

    Returns:
        list: 搜索结果列表
    """
    if not HAS_PLAYWRIGHT:
        print("请安装: pip install playwright && playwright install chromium", file=sys.stderr)
        return []

    playwright, browser = await get_browser_async()
    if not browser:
        print("无法连接Chrome", file=sys.stderr)
        return []

    results = []

    page = None
    try:
        page = await get_page_async(browser, url='https://www.baidu.com', timeout=30000)
        if not page:
            print("无法创建页面", file=sys.stderr)
            return []

        # 检查验证码
        if await check_captcha_async(page):
            print("请在浏览器窗口中完成验证...", file=sys.stderr)
            import asyncio
            for _ in range(60):
                await asyncio.sleep(1)
                if not await check_captcha_async(page):
                    print("验证完成！", file=sys.stderr)
                    break

        # 搜索
        import asyncio
        for pagenum in range(1, (limit // 10) + 2):
            pn = (pagenum - 1) * 10
            url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}&pn={pn}"

            await page.goto(url, timeout=30000, wait_until="load")
            await asyncio.sleep(2)

            if await check_captcha_async(page):
                break

            try:
                await page.wait_for_selector('div.result', timeout=10000)
            except:
                continue

            html = await page.content()

            if HAS_BS4:
                soup = BeautifulSoup(html, 'html.parser')
                for item in soup.select('div.result, div.c-container'):
                    title_tag = item.select_one('h3 a')
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        if '广告' not in title and '推广' not in title:
                            result = {
                                'title': title,
                                'url': title_tag.get('href', ''),
                                'abstract': (item.select_one('.c-abstract') or item).get_text(strip=True)[:300],
                                'score': 1.0
                            }
                            result['score'] = calculate_quality_score(result, query)
                            results.append(result)

            if len(results) >= limit:
                break

    except Exception as e:
        print(f"搜索错误: {e}", file=sys.stderr)
    finally:
        if page:
            await close_page_async(page)
        await close_browser_async(browser, playwright, keep_running=True)

    # 去重
    seen = set()
    unique = []
    for r in results:
        if r['url'] not in seen:
            seen.add(r['url'])
            unique.append(r)

    # 按质量分数排序
    unique.sort(key=lambda x: x.get('score', 1.0), reverse=True)

    return unique[:limit]


def compile_results(query, results, fetched, save_dir, session_id):
    """整理抓取结果，生成最终Markdown报告（调用markdown_writer模块）"""
    return save_search_report(query, results, fetched, save_dir, session_id)


def read_all_md_files(save_dir):
    """读取目录下所有md文件内容"""
    md_contents = {}

    if not save_dir or not os.path.exists(save_dir):
        return md_contents

    for filename in os.listdir(save_dir):
        if filename.endswith('.md') and not filename.startswith('搜索报告') and not filename.startswith('搜索总结'):
            filepath = os.path.join(save_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    md_contents[filename] = f.read()
            except Exception as e:
                print(f"读取文件失败 {filename}: {e}", file=sys.stderr)

    return md_contents


def generate_summary(query, results, md_contents, save_dir, session_id):
    """生成搜索结果总结（调用markdown_writer模块）"""
    return save_summary(query, results, md_contents, save_dir, session_id)


async def main_async():
    """异步主函数"""
    parser = argparse.ArgumentParser(description='百度搜索增强版（异步）')
    parser.add_argument('query', nargs='*', help='搜索词')
    parser.add_argument('-n', '--limit', type=int, default=50, help='搜索结果数量 (默认20)')
    parser.add_argument('-t', '--top-percent', type=float, default=35, help='按分数筛选前N%%的结果进行抓取 (默认35%%)')
    parser.add_argument('--min-score', type=float, default=1.0, help='最低分数阈值 (默认1.0)')
    parser.add_argument('-o', '--output', help='保存目录')
    parser.add_argument('--session-id', help='指定会话ID')
    parser.add_argument('-w', '--workers', type=int, default=4, help='抓取并发数')
    parser.add_argument('--json', action='store_true', help='JSON输出')
    parser.add_argument('--no-summarize', action='store_true', help='不生成总结报告')

    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        return

    query = ' '.join(args.query)

    # 创建会话目录
    session_dir, session_id = get_session_dir(args.output, args.session_id)
    print(f"搜索: {query}", file=sys.stderr)
    print(f"会话ID: {session_id}", file=sys.stderr)
    print(f"保存目录: {session_dir}", file=sys.stderr)

    # 搜索（异步）
    limit = max(args.limit, 50)
    results = await search_async(query, limit)
    print(f"找到 {len(results)} 条结果", file=sys.stderr)

    if not results:
        print("未找到搜索结果", file=sys.stderr)
        return

    # 按分数筛选
    top_count = max(1, int(len(results) * args.top_percent / 100))
    filtered_results = [r for r in results if r.get('score', 1.0) >= args.min_score]
    fetch_count = min(top_count, len(filtered_results))
    fetch_count = max(1, fetch_count)

    print(f"筛选: 分数前{args.top_percent}% + 最低{args.min_score}分 = {fetch_count}条", file=sys.stderr)

    # 抓取网页（异步并行）
    urls = [r['url'] for r in results[:fetch_count]]
    fetched = await fetch_urls_async(urls, save_dir=session_dir, workers=args.workers)
    success_count = sum(1 for r in fetched if r.get('success'))
    print(f"抓取成功: {success_count}/{len(urls)}", file=sys.stderr)

    # 生成报告
    if success_count > 0:
        compile_results(query, results, fetched, session_dir, session_id)

        if not args.no_summarize:
            md_contents = read_all_md_files(session_dir)
            if md_contents:
                summary_path = generate_summary(query, results, md_contents, session_dir, session_id)
                print(f"\n总结文件: {summary_path}", file=sys.stderr)

    # 输出结果
    if args.json:
        output = {
            'query': query,
            'session_id': session_id,
            'save_dir': session_dir,
            'total_results': len(results),
            'fetched_count': fetch_count,
            'success_count': success_count,
            'results': [
                {
                    'index': i + 1,
                    'title': r['title'],
                    'url': r['url'],
                    'score': r.get('score', 1.0),
                    'abstract': r.get('abstract', '')[:200]
                }
                for i, r in enumerate(results)
            ]
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print("\n" + "=" * 60)
        print(f"搜索结果: {query}")
        print(f"共找到 {len(results)} 条，抓取 {fetch_count} 条，成功 {success_count} 条")
        print("=" * 60)

        for i, r in enumerate(results[:20], 1):
            score = r.get('score', 1.0)
            score_indicator = "★" * min(5, int(score * 2))
            is_fetched = i <= fetch_count
            fetch_mark = "✓" if is_fetched else " "
            print(f"\n{i}. [{fetch_mark}] [{score_indicator}] {r['title']}")
            print(f"   分数: {score:.2f}")
            print(f"   链接: {r['url']}")
            if r.get('abstract'):
                abstract = r['abstract'][:100] + ('...' if len(r['abstract']) > 100 else '')
                print(f"   摘要: {abstract}")

        print("\n" + "=" * 60)
        print(f"会话目录: {session_dir}")
        print("=" * 60)


def main():
    """同步入口"""
    import asyncio
    asyncio.run(main_async())


if __name__ == '__main__':
    main()