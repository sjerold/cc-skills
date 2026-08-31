#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 列表源 - 从 JSON API 翻页拉取文章链接

适用 SPA 站点：列表由 JSON API 渲染，HTML 里没有文章 <a> 链接。
站点需在 site_configs.py 配置 'api' 字段（url/method/body_template/url_template）。

用法：
    python api_list.py <站点URL或域名> [-n 100] [-o urls.txt]

输出文章 URL 列表（-o 写文件，每行一个），可直接交给 fetcher.py --url-file 抓取。
"""

import sys
import io
import os
import json
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMMON_DIR = os.path.join(os.path.dirname(_SCRIPTS_DIR), '..', 'common', 'scripts')
sys.path.insert(0, _SCRIPTS_DIR)
sys.path.insert(0, _COMMON_DIR)

from site_configs import get_site_config


def fill_template(template, page, size):
    """填充模板占位符。用字符串替换而非 str.format，避免与 JSON 花括号冲突"""
    return template.replace('{page}', str(page)).replace('{size}', str(size))


def api_fetch_http(api, page, size):
    """用 requests 直接调用 API（优先，速度快）"""
    import requests
    url = api['url']
    method = api.get('method', 'GET').upper()
    body = fill_template(api['body_template'], page, size)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'Referer': url,
    }
    if method == 'POST':
        resp = requests.post(url, data=body.encode('utf-8'), headers=headers, timeout=20)
    else:
        resp = requests.get(url, params=json.loads(body), headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


async def api_fetch_playwright(page_ctx, api, page, size):
    """回退方案：在浏览器页面上下文中调用 API（带真实 Cookie/UA）"""
    url = api['url']
    method = api.get('method', 'GET').upper()
    body = fill_template(api['body_template'], page, size)
    js = """async ([url, method, body]) => {
        const opts = {method: method, headers: {'Content-Type': 'application/json'}};
        if (method === 'POST') { opts.body = body; }
        const resp = await fetch(url, opts);
        return await resp.json();
    }"""
    return await page_ctx.evaluate(js, [url, method, body])


def extract_records(data):
    """从 API 响应中提取 records 和 totalPage（兼容常见结构）"""
    if not isinstance(data, dict):
        return [], None
    for path in (('data', 'records'), ('records',), ('result', 'records'), ('rows',)):
        node = data
        ok = True
        for key in path[:-1]:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                ok = False
                break
        if ok and isinstance(node, dict) and path[-1] in node and isinstance(node[path[-1]], list):
            total = node.get('totalPage') or node.get('total_pages')
            return node[path[-1]], total
    return [], None


async def collect_urls(source_url, limit, page_size=10):
    """翻页拉取 API，构造 (url, title) 列表"""
    config = get_site_config(source_url)
    if not config or not config.get('api'):
        print(f"站点未配置 api: {source_url}", file=sys.stderr)
        return []

    api = config['api']
    items = []
    seen = set()
    page_no = 1
    total_page = None

    while True:
        if total_page and page_no > total_page:
            break
        if page_no > 5000:
            print("超过最大页数保护(5000)，停止", file=sys.stderr)
            break

        # 优先 requests，失败回退 playwright 上下文 fetch
        data = None
        try:
            data = api_fetch_http(api, page_no, page_size)
        except Exception as e:
            print(f"第 {page_no} 页 requests 调用失败({e.__class__.__name__})，改用 playwright", file=sys.stderr)

        if data is None:
            try:
                from chrome_manager import get_browser_async, get_page_async, close_browser_async, close_page_async
                playwright, browser = await get_browser_async()
                page_ctx = await get_page_async(browser)
                try:
                    if page_ctx.url in ('about:blank', ''):
                        await page_ctx.goto(source_url, timeout=45000)
                        await page_ctx.wait_for_load_state('domcontentloaded', timeout=15000)
                    data = await api_fetch_playwright(page_ctx, api, page_no, page_size)
                finally:
                    await close_page_async(page_ctx)
                    await close_browser_async(browser, playwright, keep_running=True)
            except Exception as e:
                print(f"第 {page_no} 页 playwright 调用也失败: {e}", file=sys.stderr)
                break

        records, total = extract_records(data)
        if total:
            total_page = total
        if not records:
            print(f"第 {page_no} 页无记录，停止", file=sys.stderr)
            break

        for rec in records:
            if not isinstance(rec, dict):
                continue
            fields = dict(rec)
            attrs = rec.get('attrs')
            if isinstance(attrs, dict):
                fields.update(attrs)
            try:
                url = api['url_template'].format(**fields)
            except KeyError as e:
                print(f"模板缺字段 {e}，跳过该记录", file=sys.stderr)
                continue
            if url not in seen:
                seen.add(url)
                items.append({'url': url, 'title': rec.get('title') or ''})

        print(f"第 {page_no}/{total_page or '?'} 页，累计 {len(items)} 条", file=sys.stderr)
        if len(items) >= limit:
            break
        page_no += 1

    return items[:limit]


def main():
    parser = argparse.ArgumentParser(description='API 列表源：从 JSON API 翻页拉取文章链接')
    parser.add_argument('url', help='站点页面 URL 或域名（用于匹配站点配置）')
    parser.add_argument('-n', '--limit', type=int, default=20, help='最大链接数量')
    parser.add_argument('-s', '--size', type=int, default=10, help='API 每页记录数')
    parser.add_argument('-o', '--output', help='URL 列表输出文件（每行一个）')
    args = parser.parse_args()

    urls = asyncio_run_collect(args.url, args.limit, args.size)

    if args.output:
        # TSV 格式：url \t title（无标题则只有 url）
        with open(args.output, 'w', encoding='utf-8') as f:
            for it in urls:
                line = f"{it['url']}\t{it['title']}" if it.get('title') else it['url']
                f.write(line + '\n')
        print(f"已写入 {len(urls)} 个URL: {args.output}", file=sys.stderr)
    else:
        for it in urls:
            print(it['url'])


def asyncio_run_collect(url, limit, size):
    import asyncio
    return asyncio.run(collect_urls(url, limit, size))


if __name__ == '__main__':
    main()
