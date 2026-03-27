#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页内容抓取脚本
支持静态网页和动态网页（使用 Playwright）
"""

import sys
import json
import io
import argparse
import os
import time
import hashlib
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import requests
except ImportError:
    print(json.dumps({'error': '请安装 requests: pip install requests'}, ensure_ascii=False))
    sys.exit(1)

HAS_BS4 = False
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    pass

# Playwright 用于动态网页
HAS_PLAYWRIGHT = False
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    pass


# ============ 工具函数 ============

def get_display_path(path):
    """将路径转换为适合当前系统的显示格式"""
    if not path:
        return path

    # Windows 系统
    if sys.platform == 'win32':
        # 处理 Git Bash 的 /tmp 映射
        if path.startswith('/tmp/'):
            import tempfile
            win_temp = tempfile.gettempdir()
            path = path.replace('/tmp/', win_temp.replace('\\', '/') + '/')

        # 将 Unix 风格路径转换为 Windows 风格
        path = path.replace('/', '\\')

    return path


# ============ 静态网页抓取 ============

def fetch_static(url, timeout=15):
    """抓取静态网页内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

        # 处理编码
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            content_type = response.headers.get('content-type', '')
            if 'charset=' in content_type:
                response.encoding = content_type.split('charset=')[-1].split(';')[0].strip()
            else:
                response.encoding = 'utf-8'

        html = response.text
        return parse_html(html, response.url)

    except Exception as e:
        return {'success': False, 'error': str(e), 'url': url}


def parse_html(html, url):
    """解析HTML提取正文"""

    if HAS_BS4:
        soup = BeautifulSoup(html, 'html.parser')

        # 移除无关元素
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript', 'form', 'button']):
            tag.decompose()

        # 提取标题
        title = ''
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)

        # 尝试提取 h1
        h1_tag = soup.find('h1')
        if h1_tag:
            h1_title = h1_tag.get_text(strip=True)
            if h1_title and len(h1_title) > len(title) * 0.5:
                title = h1_title

        # 提取 meta description
        description = ''
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            description = desc_tag.get('content', '')

        # 提取正文 - 尝试多种选择器
        content_selectors = [
            'article',
            'main',
            '.content',
            '.article',
            '.post',
            '.entry-content',
            '.post-content',
            '.article-content',
            '#content',
            '#article',
            '.main-content',
            '.text-content',
            'body'
        ]

        content_text = ''
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                # 找到内容最长的元素
                best_elem = max(elements, key=lambda e: len(e.get_text()))
                content_text = best_elem.get_text(separator='\n', strip=True)
                if len(content_text) > 200:
                    break

        if not content_text:
            content_text = soup.get_text(separator='\n', strip=True)

    else:
        # 简单正则提取
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ''

        desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        description = desc_match.group(1) if desc_match else ''

        # 移除脚本和样式
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '\n', text)
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r' +', ' ', text)
        content_text = text.strip()

    # 清理文本
    lines = [line.strip() for line in content_text.split('\n') if line.strip()]
    content_text = '\n'.join(lines)

    # 截断过长内容
    if len(content_text) > 15000:
        content_text = content_text[:15000] + '\n... (内容已截断)'

    return {
        'success': True,
        'url': url,
        'title': title,
        'description': description,
        'content': content_text,
        'length': len(content_text),
        'fetch_type': 'static'
    }


# ============ 动态网页抓取 ============

def fetch_dynamic(url, timeout=30, wait_time=3):
    """使用 Playwright 抓取动态网页"""
    if not HAS_PLAYWRIGHT:
        return {
            'success': False,
            'error': 'Playwright 未安装。请运行: pip install playwright && playwright install chromium',
            'url': url
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()

            # 设置超时
            page.set_default_timeout(timeout * 1000)

            # 访问页面
            page.goto(url, wait_until='networkidle')

            # 等待内容加载
            time.sleep(wait_time)

            # 获取渲染后的 HTML
            html = page.content()
            final_url = page.url

            browser.close()

            # 解析内容
            result = parse_html(html, final_url)
            result['fetch_type'] = 'dynamic'
            return result

    except PlaywrightTimeout:
        return {
            'success': False,
            'error': '页面加载超时',
            'url': url
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'url': url
        }


# ============ 智能抓取 ============

def smart_fetch(url, use_dynamic='auto', timeout=15, wait_time=3):
    """智能抓取：自动判断是否需要动态渲染"""

    # 如果明确指定动态抓取
    if use_dynamic == 'always':
        return fetch_dynamic(url, timeout, wait_time)

    # 如果明确指定静态抓取
    if use_dynamic == 'never':
        return fetch_static(url, timeout)

    # 自动模式：先尝试静态，如果内容太少则尝试动态
    result = fetch_static(url, timeout)

    if result['success']:
        content_len = result.get('length', 0)

        # 如果内容太少（可能需要JS渲染），尝试动态抓取
        if content_len < 500 and HAS_PLAYWRIGHT:
            dynamic_result = fetch_dynamic(url, timeout, wait_time)
            if dynamic_result['success'] and dynamic_result.get('length', 0) > content_len * 1.5:
                return dynamic_result

    return result


# ============ 批量抓取 ============

def fetch_batch(urls, use_dynamic='auto', max_workers=3, save_dir=None, timeout=15):
    """批量抓取多个URL"""

    def fetch_one(url):
        result = smart_fetch(url, use_dynamic, timeout)
        return result

    results = []

    # 动态抓取不支持多线程，串行执行
    if use_dynamic == 'always' or (use_dynamic == 'auto' and HAS_PLAYWRIGHT):
        for i, url in enumerate(urls):
            print(f"抓取 [{i+1}/{len(urls)}]: {url[:50]}...", file=sys.stderr)
            result = fetch_one(url)

            # 保存文件
            if save_dir and result['success']:
                filepath = save_content(result, save_dir)
                result['local_file'] = get_display_path(filepath)

            results.append(result)
    else:
        # 静态抓取可以并发
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_one, url): url for url in urls}

            for future in as_completed(futures):
                try:
                    result = future.result()

                    if save_dir and result['success']:
                        filepath = save_content(result, save_dir)
                        result['local_file'] = filepath

                    results.append(result)
                except Exception as e:
                    results.append({
                        'success': False,
                        'error': str(e),
                        'url': futures[future]
                    })

    return results


def save_content(result, save_dir):
    """保存内容到文件"""
    os.makedirs(save_dir, exist_ok=True)

    url_hash = hashlib.md5(result['url'].encode()).hexdigest()[:8]
    # 清理标题用于文件名
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', result.get('title', 'untitled'))[:50]
    filename = f"{safe_title}_{url_hash}.txt"
    filepath = os.path.join(save_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"标题: {result.get('title', 'N/A')}\n")
        f.write(f"URL: {result['url']}\n")
        f.write(f"描述: {result.get('description', 'N/A')}\n")
        f.write(f"抓取时间: {datetime.now().isoformat()}\n")
        f.write(f"抓取方式: {result.get('fetch_type', 'static')}\n")
        f.write("=" * 60 + "\n\n")
        f.write(result['content'])

    return filepath


# ============ 主函数 ============

def main():
    parser = argparse.ArgumentParser(description='网页内容抓取工具')
    parser.add_argument('urls', nargs='+', help='要抓取的URL')
    parser.add_argument('-d', '--dynamic', choices=['auto', 'always', 'never'], default='auto',
                        help='动态渲染模式: auto(自动判断), always(总是动态), never(仅静态)')
    parser.add_argument('-w', '--wait', type=int, default=3, help='动态渲染等待时间(秒)')
    parser.add_argument('-t', '--timeout', type=int, default=15, help='请求超时时间(秒)')
    parser.add_argument('-o', '--output', type=str, help='保存内容的目录')
    parser.add_argument('--max-workers', type=int, default=3, help='并发数(仅静态抓取)')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')

    args = parser.parse_args()

    save_dir = None
    if args.output:
        save_dir = os.path.expanduser(args.output)

    results = fetch_batch(
        args.urls,
        use_dynamic=args.dynamic,
        max_workers=args.max_workers,
        save_dir=save_dir,
        timeout=args.timeout
    )

    # 统计
    success_count = sum(1 for r in results if r['success'])
    total_length = sum(r.get('length', 0) for r in results if r['success'])

    output = {
        'total': len(results),
        'success': success_count,
        'failed': len(results) - success_count,
        'total_length': total_length,
        'save_dir': get_display_path(save_dir) if save_dir else None,
        'results': results
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"\n抓取完成: {success_count}/{len(results)} 成功")
        if save_dir:
            print(f"内容已保存到: {get_display_path(save_dir)}")
        print()

        for i, r in enumerate(results, 1):
            status = "✓" if r['success'] else "✗"
            print(f"{i}. {status} {r.get('title', r['url'][:50])}")
            if r['success']:
                print(f"   长度: {r.get('length', 0)} 字符")
                if r.get('local_file'):
                    print(f"   文件: {r['local_file']}")
            else:
                print(f"   错误: {r.get('error', 'Unknown')}")


if __name__ == '__main__':
    main()