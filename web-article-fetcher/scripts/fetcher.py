#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页文章抓取工具 - Clean Code 版本

功能：
1. 从源页面发现文章链接
2. 异步并行抓取
3. 增量更新（避免重复抓取）
4. 保存为 Markdown

用法：
    fetcher.py <url> [-n 20] [-w 4]
    fetcher.py <url1> <url2> ...  # 直接抓取多个URL
"""

import sys
import json
import io
import re
import os
import asyncio
import argparse
from datetime import datetime
from pathlib import Path

# UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 导入本地模块
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)

from site_configs import SITE_ALIASES, SITE_CONFIGS, get_site_config, get_site_name
from link_discovery import discover_links

# 导入 common 模块
_COMMON_DIR = os.path.join(os.path.dirname(_SCRIPTS_DIR), '..', 'common', 'scripts')
sys.path.insert(0, _COMMON_DIR)

try:
    from chrome_manager import get_browser_async, get_page_async, close_browser_async, close_page_async
    from web_fetcher import fetch_url_async
    from markdown_writer import save_result_to_markdown, sanitize_filename, generate_hash
    HAS_COMMON = True
except ImportError as e:
    print(f"common 模块导入失败: {e}", file=sys.stderr)
    HAS_COMMON = False

# ============ 配置 ============

DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser('~/Downloads'), 'web_article_fetcher')
STATE_FILE_NAME = '.fetched_urls.json'

# ============ 状态管理 ============

def load_state(filepath):
    """加载抓取状态"""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {'version': '1.0', 'urls': {}}

def save_state(state, filepath):
    """保存抓取状态"""
    state['last_update'] = datetime.now().isoformat()
    state['total_count'] = len(state.get('urls', {}))
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def clear_state(filepath):
    """清空状态"""
    if os.path.exists(filepath):
        os.remove(filepath)

def is_fetched(url, state):
    """检查URL是否已抓取"""
    url_hash = generate_hash(url) if HAS_COMMON else url[-8:]
    return url_hash in state.get('urls', {})

def add_fetched(state, url, info):
    """添加已抓取记录"""
    url_hash = generate_hash(url) if HAS_COMMON else url[-8:]
    state.setdefault('urls', {})[url_hash] = {
        'url': url,
        'title': info.get('title'),
        'fetch_time': datetime.now().isoformat(),
        'file': info.get('file')
    }

# ============ 源页面获取 ============

async def fetch_source_page(url):
    """获取源页面HTML"""
    if not HAS_COMMON:
        return None, None

    browser = None
    page = None
    try:
        playwright, browser = await get_browser_async()
        if not browser:
            return None, None

        page = await get_page_async(browser)
        if not page:
            return None, None

        await page.goto(url, timeout=30000)
        await page.wait_for_load_state('networkidle', timeout=10000)
        html = await page.content()
        return html, page.url

    except Exception as e:
        print(f"获取源页面失败: {e}", file=sys.stderr)
        return None, None
    finally:
        if page:
            await close_page_async(page)
        if browser:
            await close_browser_async(browser, playwright if 'playwright' in dir() else None, keep_running=True)

# ============ 文章保存 ============

def save_article(result, save_dir, site_name):
    """保存文章为Markdown"""
    if not HAS_COMMON:
        return None

    url = result.get('original_url') or result.get('url', '')
    title = result.get('title', 'untitled')
    safe_title = sanitize_filename(title, max_length=50)

    # 提取URL中的日期时间
    datetime_match = re.search(r'/(\d{6})/(\d{6,8})\.html', url)
    if datetime_match:
        url_datetime = f"{datetime_match.group(1)}_{datetime_match.group(2)}"
        filename = f"{url_datetime}_{site_name}_{safe_title}"
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        url_hash = generate_hash(url)
        filename = f"{timestamp}_{site_name}_{safe_title}_{url_hash}"

    # 保存到站点子目录
    site_dir = os.path.join(save_dir, site_name)
    os.makedirs(site_dir, exist_ok=True)

    result['source'] = site_name
    return save_result_to_markdown(result, site_dir, filename)

# ============ 报告生成 ============

def generate_report(results, discovered, skipped, save_dir, source_url, site_name):
    """生成抓取报告"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(save_dir, f"抓取报告_{timestamp}.md")

    success = sum(1 for r in results if r.get('success'))

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# 网页文章抓取报告\n\n")
        f.write(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## 抓取概况\n\n")
        f.write(f"- **源页面**: {source_url}\n")
        f.write(f"- **站点**: {site_name}\n")
        f.write(f"- **发现链接**: {discovered}\n")
        f.write(f"- **跳过已抓取**: {skipped}\n")
        f.write(f"- **本次抓取**: {len(results)}\n")
        f.write(f"- **成功**: {success}\n")
        f.write(f"- **失败**: {len(results) - success}\n\n")
        f.write(f"## 抓取结果\n\n")

        for r in results:
            status = "✓" if r.get('success') else "✗"
            f.write(f"- {status} [{r.get('title', 'N/A')[:40]}]({r.get('url')})\n")

    return report_path

# ============ 主流程 ============

async def fetch_urls_directly(urls, save_dir, state_file, workers):
    """直接抓取模式：抓取指定的URL列表"""
    state = load_state(state_file)
    results = []
    semaphore = asyncio.Semaphore(workers)

    async def fetch_one(idx, url):
        async with semaphore:
            result = await fetch_url_async(url)
            results.append(result)

            if result.get('success'):
                site_name = get_site_name(url)
                filepath = save_article(result, save_dir, site_name)
                if filepath:
                    result['file'] = filepath
                    print(f"  [{idx+1}/{len(urls)}] 已保存: {result.get('title', '')[:30]}", file=sys.stderr)
                add_fetched(state, url, {'title': result.get('title'), 'file': filepath})
                save_state(state, state_file)
            else:
                print(f"  [{idx+1}/{len(urls)}] 失败: {result.get('error', 'Unknown')}", file=sys.stderr)

            return result

    tasks = [fetch_one(i, url) for i, url in enumerate(urls)]
    await asyncio.gather(*tasks)

    return results


async def fetch_from_source(source_url, limit, save_dir, state_file, workers, full_mode):
    """从源页面发现并抓取"""
    state = load_state(state_file)
    if full_mode:
        clear_state(state_file)
        state = {'version': '1.0', 'urls': {}}

    # 获取源页面
    html, _ = await fetch_source_page(source_url)
    if not html:
        print("无法获取源页面", file=sys.stderr)
        return []

    # 发现链接
    config = get_site_config(source_url)
    discovered = discover_links(source_url, html, config)
    print(f"发现 {len(discovered)} 个链接", file=sys.stderr)

    # 增量过滤
    to_fetch = [item for item in discovered if not is_fetched(item['url'], state)]
    skipped = len(discovered) - len(to_fetch)
    print(f"跳过 {skipped} 个已抓取，待抓取 {len(to_fetch)} 个", file=sys.stderr)

    # 限制数量
    to_fetch = to_fetch[:limit]

    if not to_fetch:
        print("没有新文章", file=sys.stderr)
        return []

    # 抓取
    urls = [item['url'] for item in to_fetch]
    site_name = config.get('name') if config else get_site_name(source_url)
    results = []
    semaphore = asyncio.Semaphore(workers)

    async def fetch_one(idx, url):
        async with semaphore:
            result = await fetch_url_async(url)
            results.append(result)

            if result.get('success'):
                filepath = save_article(result, save_dir, site_name)
                if filepath:
                    result['file'] = filepath
                    print(f"  [{idx+1}/{len(urls)}] 已保存: {result.get('title', '')[:30]}", file=sys.stderr)
                add_fetched(state, url, {'title': result.get('title'), 'file': filepath})
                save_state(state, state_file)
            else:
                print(f"  [{idx+1}/{len(urls)}] 失败: {result.get('error', 'Unknown')}", file=sys.stderr)

            return result

    tasks = [fetch_one(i, url) for i, url in enumerate(urls)]
    await asyncio.gather(*tasks)

    # 生成报告
    generate_report(results, len(discovered), skipped, save_dir, source_url, site_name)

    return results


async def main():
    """主入口"""
    parser = argparse.ArgumentParser(description='网页文章抓取工具')
    parser.add_argument('url', nargs='*', help='源页面URL或文章URL（支持多个）')
    parser.add_argument('-n', '--limit', type=int, default=20, help='最大抓取数量')
    parser.add_argument('-o', '--output', help='保存目录')
    parser.add_argument('--full', action='store_true', help='全量抓取')
    parser.add_argument('-w', '--workers', type=int, default=4, help='并发数')

    args = parser.parse_args()

    if not args.url:
        parser.print_help()
        return

    if not HAS_COMMON:
        print("错误: common 模块不可用", file=sys.stderr)
        return

    # 设置保存目录
    save_dir = os.path.expanduser(args.output) if args.output else DEFAULT_OUTPUT_DIR
    os.makedirs(save_dir, exist_ok=True)
    state_file = os.path.join(save_dir, STATE_FILE_NAME)

    # 解析URL
    urls = []
    for u in args.url:
        if u in SITE_ALIASES:
            urls.append(SITE_ALIASES[u])
        elif not u.startswith(('http://', 'https://')):
            urls.append('https://' + u)
        else:
            urls.append(u)

    print(f"保存目录: {save_dir}", file=sys.stderr)
    print(f"并发数: {args.workers}", file=sys.stderr)

    # 判断模式
    if len(urls) > 1:
        print(f"直接抓取模式: {len(urls)} 个URL", file=sys.stderr)
        results = await fetch_urls_directly(urls, save_dir, state_file, args.workers)
    else:
        source_url = urls[0]
        print(f"源页面: {source_url}", file=sys.stderr)
        print(f"最大抓取: {args.limit}", file=sys.stderr)
        results = await fetch_from_source(source_url, args.limit, save_dir, state_file, args.workers, args.full)

    # 统计
    success = sum(1 for r in results if r.get('success'))
    print(f"\n抓取完成: {success}/{len(results)} 成功", file=sys.stderr)


if __name__ == '__main__':
    asyncio.run(main())