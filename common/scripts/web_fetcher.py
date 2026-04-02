#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页抓取模块 - 统一的网页内容抓取

使用chrome_manager连接现有Chrome，在新tab中抓取内容。
复用用户的登录状态和Cookie。

使用方式：
    from web_fetcher import fetch_url, fetch_urls

    result = fetch_url('https://example.com')
    results = fetch_urls(['url1', 'url2'], save_dir='./output')
"""

import sys
import os
import re
import time
import hashlib
import json
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入chrome_manager
try:
    from chrome_manager import get_browser, get_page, close_browser, HAS_PLAYWRIGHT
except ImportError:
    # 如果直接运行，添加当前目录到path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from chrome_manager import get_browser, get_page, close_browser, HAS_PLAYWRIGHT

# 尝试导入BS4
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# 尝试导入requests（备用静态抓取）
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def extract_content(html, url=''):
    """从HTML中提取正文内容

    Args:
        html: HTML内容
        url: 原始URL（用于日志）

    Returns:
        dict: {title, content, length}
    """
    if HAS_BS4:
        soup = BeautifulSoup(html, 'html.parser')

        # 移除无用标签
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
            tag.decompose()

        # 提取标题
        title = ''
        if soup.find('title'):
            title = soup.find('title').get_text(strip=True)
        elif soup.find('h1'):
            title = soup.find('h1').get_text(strip=True)

        # 提取正文 - 尝试多个选择器
        content_text = ''
        content_selectors = [
            'article', 'main', '.content', '.article', '.post',
            '.entry-content', '.post-content', '#content',
            '.article-content', '.detail', '.body'
        ]

        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                # 选择内容最长的元素
                best_elem = max(elements, key=lambda e: len(e.get_text()))
                content_text = best_elem.get_text(separator='\n', strip=True)
                if len(content_text) > 200:
                    break

        # 如果没找到，用body
        if not content_text and soup.find('body'):
            content_text = soup.find('body').get_text(separator='\n', strip=True)

    else:
        # 无BS4，用正则
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ''

        # 移除script和style
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '\n', text)
        content_text = re.sub(r'\n+', '\n', text).strip()

    # 清理内容
    content_text = '\n'.join(line.strip() for line in content_text.split('\n') if line.strip())

    # 截断过长内容
    max_length = 15000
    if len(content_text) > max_length:
        content_text = content_text[:max_length] + '\n... (内容已截断)'

    return {
        'title': title,
        'content': content_text,
        'length': len(content_text)
    }


def check_anti_crawl(html, url=''):
    """检测是否遇到反爬/验证码

    Args:
        html: HTML内容
        url: 当前URL

    Returns:
        bool: True表示遇到反爬
    """
    html_lower = html.lower()
    url_lower = url.lower()

    anti_patterns = [
        '百度安全验证', '安全验证', '验证码', 'captcha',
        'wappass.baidu.com', '请输入验证码', '访问过于频繁',
        '人机验证', '滑块验证', 'security check',
        'cloudflare', '验证您的身份'
    ]

    for pattern in anti_patterns:
        if pattern in html_lower or pattern in url_lower:
            return True

    return False


def _fetch_single_static(url):
    """静态抓取单个URL（用于线程池）"""
    result = {
        'success': False,
        'url': url,
        'original_url': url,
        'title': '',
        'content': '',
        'length': 0,
        'error': None,
        'anti_crawl': False,
        'fetch_type': ''
    }

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)

        # 修复编码问题
        if resp.encoding is None or resp.encoding.lower() == 'iso-8859-1':
            content_type = resp.headers.get('content-type', '')
            charset_match = re.search(r'charset=([^\s;]+)', content_type, re.IGNORECASE)
            if charset_match:
                resp.encoding = charset_match.group(1)
            else:
                content_bytes = resp.content
                meta_match = re.search(r'<meta[^>]+charset=["\']?([^"\'>\s]+)',
                                      content_bytes[:1000].decode('utf-8', errors='ignore'),
                                      re.IGNORECASE)
                if meta_match:
                    resp.encoding = meta_match.group(1)
                else:
                    resp.encoding = 'utf-8'

        try:
            html = resp.content.decode(resp.encoding or 'utf-8', errors='replace')
        except:
            html = resp.content.decode('utf-8', errors='replace')

        content_data = extract_content(html, resp.url)
        result['success'] = True
        result['title'] = content_data['title']
        result['content'] = content_data['content']
        result['length'] = content_data['length']
        result['url'] = resp.url
        result['fetch_type'] = 'static'

    except Exception as e:
        result['error'] = str(e)

    return result


def fetch_url(url, timeout=30000, wait_time=2):
    """抓取单个URL的内容

    Args:
        url: 要抓取的URL
        timeout: 页面加载超时（毫秒）
        wait_time: 等待JS渲染的时间（秒）

    Returns:
        dict: {success, title, content, url, length, error, anti_crawl}
    """
    result = {
        'success': False,
        'url': url,
        'original_url': url,
        'title': '',
        'content': '',
        'length': 0,
        'error': None,
        'anti_crawl': False,
        'fetch_type': ''
    }

    if HAS_PLAYWRIGHT:
        # 使用Playwright抓取（推荐）
        browser = get_browser()
        if not browser:
            result['error'] = '无法连接Chrome'
            return result

        page = None
        try:
            page = get_page(browser, timeout=timeout)
            if not page:
                result['error'] = '无法创建页面'
                return result

            print(f"抓取: {url[:60]}...", file=sys.stderr)
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            time.sleep(wait_time)

            # 等待网络空闲
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass

            final_url = page.url
            html = page.content()

            # 检测反爬
            if check_anti_crawl(html, final_url):
                result['anti_crawl'] = True
                result['error'] = '遇到反爬限制'
                result['url'] = final_url
            else:
                content_data = extract_content(html, final_url)
                result['success'] = True
                result['title'] = content_data['title']
                result['content'] = content_data['content']
                result['length'] = content_data['length']
                result['url'] = final_url
                result['fetch_type'] = 'playwright'

        except Exception as e:
            result['error'] = str(e)

        finally:
            # 关闭页面
            if page:
                try:
                    page.close()
                except:
                    pass
            close_browser(browser, keep_running=True)

    elif HAS_REQUESTS:
        # 静态抓取（备用）
        print(f"静态抓取: {url[:60]}...", file=sys.stderr)
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36'
            }
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)

            # 修复编码问题：显式检测并设置正确编码
            # requests 自动检测的编码可能不准确，特别是中文网页
            if resp.encoding is None or resp.encoding.lower() == 'iso-8859-1':
                # 从 content 或 headers 检测真实编码
                content_type = resp.headers.get('content-type', '')
                charset_match = re.search(r'charset=([^\s;]+)', content_type, re.IGNORECASE)
                if charset_match:
                    resp.encoding = charset_match.group(1)
                else:
                    # 从 HTML meta 标签检测
                    content_bytes = resp.content
                    meta_match = re.search(r'<meta[^>]+charset=["\']?([^"\'>\s]+)',
                                          content_bytes[:1000].decode('utf-8', errors='ignore'),
                                          re.IGNORECASE)
                    if meta_match:
                        resp.encoding = meta_match.group(1)
                    else:
                        # 默认 UTF-8
                        resp.encoding = 'utf-8'

            # 强制使用 UTF-8 处理中文网页
            try:
                html = resp.content.decode(resp.encoding or 'utf-8', errors='replace')
            except:
                html = resp.content.decode('utf-8', errors='replace')

            content_data = extract_content(html, resp.url)
            result['success'] = True
            result['title'] = content_data['title']
            result['content'] = content_data['content']
            result['length'] = content_data['length']
            result['url'] = resp.url
            result['fetch_type'] = 'static'

        except Exception as e:
            result['error'] = str(e)

    else:
        result['error'] = 'Playwright和requests均未安装'

    return result


def fetch_urls(urls, save_dir=None, delay=1.0, timeout=30000, workers=3):
    """批量抓取URL

    Args:
        urls: URL列表
        save_dir: 保存目录（可选，保存为Markdown文件）
        delay: 请求间隔（秒）
        timeout: 超时时间
        workers: 静态抓取线程数（默认3）

    Returns:
        list: 抓取结果列表
    """
    results = []

    # 连接浏览器（一次性连接，批量抓取）
    browser = None
    if HAS_PLAYWRIGHT:
        browser = get_browser()

    # 使用线程池并行静态抓取
    if browser is None and HAS_REQUESTS and workers > 1:
        print(f"使用 {workers} 线程并行抓取 {len(urls)} 个URL", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_url = {executor.submit(_fetch_single_static, url): url for url in urls}
            for future in as_completed(future_to_url):
                result = future.result()
                if result.get('success') and save_dir:
                    save_result_to_markdown(result, save_dir)
                results.append(result)
        # 按原始顺序排序
        url_to_result = {r['original_url']: r for r in results}
        results = [url_to_result.get(url, {'success': False, 'url': url, 'error': '未抓取'}) for url in urls]
        close_browser(None, keep_running=True)
        return results

    try:
        for i, url in enumerate(urls):
            print(f"抓取 [{i+1}/{len(urls)}]: {url[:50]}...", file=sys.stderr)

            if delay and i > 0:
                time.sleep(delay)

            result = {
                'success': False,
                'url': url,
                'original_url': url,
                'title': '',
                'content': '',
                'length': 0,
                'error': None,
                'anti_crawl': False,
                'fetch_type': ''
            }

            if browser:
                # Playwright抓取
                page = None
                try:
                    page = get_page(browser, timeout=timeout)
                    if not page:
                        result['error'] = '无法创建页面'
                        results.append(result)
                        continue

                    page.goto(url, timeout=timeout, wait_until="domcontentloaded")
                    time.sleep(2)

                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        pass

                    # 滚动加载动态内容
                    try:
                        for scroll_times in range(5):  # 最多滚动5次
                            old_height = page.evaluate("document.body.scrollHeight")
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(1)  # 等待加载
                            new_height = page.evaluate("document.body.scrollHeight")
                            if new_height == old_height:
                                break  # 没有新内容了
                    except:
                        pass

                    # 滚动回顶部
                    try:
                        page.evaluate("window.scrollTo(0, 0)")
                    except:
                        pass

                    final_url = page.url
                    html = page.content()

                    if check_anti_crawl(html, final_url):
                        result['anti_crawl'] = True
                        result['error'] = '遇到反爬限制'
                        result['url'] = final_url
                    else:
                        content_data = extract_content(html, final_url)
                        result['success'] = True
                        result['title'] = content_data['title']
                        result['content'] = content_data['content']
                        result['length'] = content_data['length']
                        result['url'] = final_url
                        result['fetch_type'] = 'playwright'

                except Exception as e:
                    result['error'] = str(e)
                finally:
                    # 确保页面关闭
                    if page:
                        try:
                            page.close()
                        except:
                            pass

            elif HAS_REQUESTS:
                # 静态抓取
                try:
                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
                    resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)

                    # 修复编码问题
                    if resp.encoding is None or resp.encoding.lower() == 'iso-8859-1':
                        content_type = resp.headers.get('content-type', '')
                        charset_match = re.search(r'charset=([^\s;]+)', content_type, re.IGNORECASE)
                        if charset_match:
                            resp.encoding = charset_match.group(1)
                        else:
                            content_bytes = resp.content
                            meta_match = re.search(r'<meta[^>]+charset=["\']?([^"\'>\s]+)',
                                                  content_bytes[:1000].decode('utf-8', errors='ignore'),
                                                  re.IGNORECASE)
                            if meta_match:
                                resp.encoding = meta_match.group(1)
                            else:
                                resp.encoding = 'utf-8'

                    try:
                        html = resp.content.decode(resp.encoding or 'utf-8', errors='replace')
                    except:
                        html = resp.content.decode('utf-8', errors='replace')

                    content_data = extract_content(html, resp.url)
                    result['success'] = True
                    result['title'] = content_data['title']
                    result['content'] = content_data['content']
                    result['length'] = content_data['length']
                    result['url'] = resp.url
                    result['fetch_type'] = 'static'

                except Exception as e:
                    result['error'] = str(e)

            else:
                result['error'] = 'Playwright和requests均未安装'

            # 保存为Markdown
            if result['success'] and save_dir:
                save_result_to_markdown(result, save_dir)

            results.append(result)

    finally:
        if browser:
            close_browser(browser, keep_running=True)

    return results


def save_result_to_markdown(result, save_dir):
    """将抓取结果保存为Markdown文件

    Args:
        result: 抓取结果dict
        save_dir: 保存目录

    Returns:
        str: 保存的文件路径
    """
    if not result.get('success') or not result.get('content'):
        return None

    os.makedirs(save_dir, exist_ok=True)

    # 生成文件名
    title = result.get('title', 'untitled')
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:50]
    url_hash = hashlib.md5(result['original_url'].encode()).hexdigest()[:8]
    filename = f"{safe_title}_{url_hash}.md"
    filepath = os.path.join(save_dir, filename)

    # 写入文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {title}\n\n")
        f.write(f"- **URL**: {result.get('url', '')}\n")
        f.write(f"- **原始URL**: {result['original_url']}\n")
        f.write(f"- **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **抓取方式**: {result.get('fetch_type', '')}\n")
        f.write(f"- **内容长度**: {result['length']} 字符\n\n")
        f.write("---\n\n")
        f.write("## 正文内容\n\n")
        f.write(result['content'])

    result['file'] = filepath
    print(f"已保存: {filepath}", file=sys.stderr)
    return filepath


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='网页抓取工具')
    parser.add_argument('url', nargs='*', help='要抓取的URL')
    parser.add_argument('-o', '--output', help='保存目录')
    parser.add_argument('--test', action='store_true', help='测试抓取百度')

    args = parser.parse_args()

    if args.test:
        result = fetch_url('https://www.baidu.com')
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.url:
        urls = args.url
        results = fetch_urls(urls, save_dir=args.output)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    else:
        parser.print_help()