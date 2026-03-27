#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页内容抓取脚本 - 复制Chrome配置版
支持后台运行(headless)和自动关闭浏览器
"""

import sys
import json
import io
import argparse
import os
import time
import hashlib
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

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

HAS_PLAYWRIGHT = False
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    pass


# ============ 配置 ============

CHROME_DEBUG_PORT = 9224  # 使用不同端口避免与baidu_search冲突

# Chrome配置目录
if sys.platform == 'win32':
    CHROME_USER_DATA_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')
    TEMP_CHROME_DIR = os.path.join(os.environ['TEMP'], 'chrome-fetch-profile')
else:
    CHROME_USER_DATA_DIR = os.path.expanduser('~/.config/google-chrome')
    TEMP_CHROME_DIR = '/tmp/chrome-fetch-profile'

# 需要复制的目录
COPY_DIRS = ['Default', 'Profile 1', 'Profile 2']

# Chrome进程PID文件
CHROME_PID_FILE = os.path.join(TEMP_CHROME_DIR, '.chrome_pid')

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'


# ============ Chrome管理 ============

def get_chrome_path():
    """获取Chrome路径"""
    if sys.platform == 'win32':
        paths = [
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        ]
        for p in paths:
            if os.path.exists(p):
                return p
    return 'chrome'


def check_port_in_use(port):
    """检查端口"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0


def copy_chrome_profile():
    """复制Chrome配置到临时目录"""
    print("正在复制Chrome配置...", file=sys.stderr)

    # 如果已有临时目录，先删除
    if os.path.exists(TEMP_CHROME_DIR):
        try:
            shutil.rmtree(TEMP_CHROME_DIR)
        except:
            pass

    os.makedirs(TEMP_CHROME_DIR, exist_ok=True)

    copied_count = 0
    for dir_name in COPY_DIRS:
        src = os.path.join(CHROME_USER_DATA_DIR, dir_name)
        dst = os.path.join(TEMP_CHROME_DIR, dir_name)
        if os.path.exists(src):
            try:
                # 只复制关键文件，跳过大文件和锁定文件
                shutil.copytree(src, dst,
                    ignore=shutil.ignore_patterns(
                        'Cache*', 'GPUCache*', 'Code Cache*',
                        'DawnGraphiteCache*', 'DawnWebGPUCache*',
                        '*.lock', 'LOCK', 'lockfile',
                        'Session Storage', 'IndexedDB', 'File System'
                    ))
                copied_count += 1
                print(f"  复制 {dir_name} 成功", file=sys.stderr)
            except Exception as e:
                print(f"  警告: {dir_name} 部分文件复制失败", file=sys.stderr)

    print(f"配置复制完成 (复制了 {copied_count} 个配置)", file=sys.stderr)
    return TEMP_CHROME_DIR


def start_chrome(headless=True):
    """启动Chrome调试模式

    Args:
        headless: True=后台运行，False=显示窗口
    """
    if check_port_in_use(CHROME_DEBUG_PORT):
        print(f"Chrome调试端口 {CHROME_DEBUG_PORT} 已可用", file=sys.stderr)
        return True

    # 复制配置
    profile_dir = copy_chrome_profile()

    chrome_path = get_chrome_path()
    cmd = [
        chrome_path,
        f"--remote-debugging-port={CHROME_DEBUG_PORT}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
        "--metrics-recording-only",
        "--disable-default-apps",
    ]

    if headless:
        cmd.append("--headless=new")

    try:
        # 保存PID到文件
        os.makedirs(TEMP_CHROME_DIR, exist_ok=True)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )

        # 保存PID
        with open(CHROME_PID_FILE, 'w') as f:
            f.write(str(proc.pid))

        for _ in range(30):
            time.sleep(0.5)
            if check_port_in_use(CHROME_DEBUG_PORT):
                mode = "后台模式" if headless else "窗口模式"
                print(f"Chrome已启动 ({mode})，PID: {proc.pid}", file=sys.stderr)
                return True

        return False
    except Exception as e:
        print(f"启动Chrome失败: {e}", file=sys.stderr)
        return False


def close_chrome():
    """关闭Chrome调试进程"""
    pid = None

    # 读取保存的PID
    if os.path.exists(CHROME_PID_FILE):
        try:
            with open(CHROME_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.remove(CHROME_PID_FILE)
        except:
            pass

    # 如果没有PID文件，尝试从端口获取
    if not pid and check_port_in_use(CHROME_DEBUG_PORT):
        try:
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if f':{CHROME_DEBUG_PORT}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = int(parts[-1])
                        break
        except:
            pass

    if pid:
        try:
            subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                          capture_output=True, timeout=5)
            print(f"Chrome已关闭 (PID: {pid})", file=sys.stderr)
        except Exception as e:
            print(f"关闭Chrome失败: {e}", file=sys.stderr)

    # 等待端口释放
    time.sleep(1)

    # 最终检查
    if check_port_in_use(CHROME_DEBUG_PORT):
        print("Chrome端口仍在使用", file=sys.stderr)
    else:
        print("Chrome调试进程已清理", file=sys.stderr)


# ============ 静态抓取 ============

def fetch_static(url, timeout=15):
    """静态抓取网页内容"""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

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


# ============ 动态抓取 (Playwright + Chrome CDP) ============

def fetch_with_chrome(url, timeout=30, wait_time=2, headless=True):
    """使用Chrome浏览器抓取网页

    Args:
        url: 目标URL
        timeout: 超时时间
        wait_time: 等待页面加载时间
        headless: True=后台运行，False=显示窗口
    """
    if not HAS_PLAYWRIGHT:
        return {
            'success': False,
            'error': 'Playwright未安装。请运行: pip install playwright',
            'url': url
        }

    if not start_chrome(headless=headless):
        return {
            'success': False,
            'error': 'Chrome启动失败',
            'url': url
        }

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f'http://127.0.0.1:{CHROME_DEBUG_PORT}')
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()

            page.set_default_timeout(timeout * 1000)

            print(f"正在访问: {url[:60]}...", file=sys.stderr)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)

            # 等待页面加载
            time.sleep(wait_time)

            # 等待网络空闲
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass

            html = page.content()
            final_url = page.url

            result = parse_html(html, final_url)
            result['fetch_type'] = 'chrome_cdp'
            return result

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'url': url
        }
    finally:
        # 通过Playwright关闭浏览器
        if browser:
            try:
                browser.close()
                print("Chrome已关闭", file=sys.stderr)
            except:
                # 如果Playwright关闭失败，使用系统方法
                close_chrome()


def parse_html(html, url):
    """解析HTML提取正文"""

    # 检测反爬/验证码页面
    anti_patterns = [
        '百度安全验证', '安全验证', '验证码', 'captcha',
        'wappass.baidu.com', '请输入验证码', '访问过于频繁', '人机验证',
    ]
    for pattern in anti_patterns:
        if pattern.lower() in html.lower():
            return {
                'success': False,
                'error': f'遇到反爬限制: {pattern}',
                'url': url,
                'anti_crawl': True
            }

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

        # 提取正文
        content_selectors = [
            'article', 'main', '.content', '.article', '.post',
            '.entry-content', '.post-content', '.article-content',
            '#content', '#article', '.main-content', '.text-content',
            'body'
        ]

        content_text = ''
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
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

    # 检测内容是否有效
    if len(title) < 2 and len(content_text) < 100:
        return {
            'success': False,
            'error': '页面内容为空或过短，可能被反爬阻止',
            'url': url,
            'anti_crawl': True
        }

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


# ============ 智能抓取 ============

def smart_fetch(url, use_chrome='auto', timeout=15, wait_time=2, headless=True):
    """智能抓取：自动判断是否需要使用Chrome

    Args:
        url: 目标URL
        use_chrome: 'auto'=自动判断, 'always'=总是用Chrome, 'never'=仅静态
        timeout: 超时时间
        wait_time: 等待时间
        headless: True=后台运行，False=显示窗口
    """

    if use_chrome == 'always':
        return fetch_with_chrome(url, timeout, wait_time, headless)

    if use_chrome == 'never':
        return fetch_static(url, timeout)

    # 自动模式：先尝试静态，如果内容太少或遇到反爬则使用Chrome
    result = fetch_static(url, timeout)

    if result['success']:
        content_len = result.get('length', 0)

        # 如果内容太少或检测到反爬特征，尝试Chrome
        if content_len < 500 or result.get('anti_crawl'):
            if HAS_PLAYWRIGHT:
                chrome_result = fetch_with_chrome(url, timeout, wait_time, headless)
                if chrome_result['success'] and chrome_result.get('length', 0) > content_len * 1.2:
                    return chrome_result

    elif result.get('anti_crawl') and HAS_PLAYWRIGHT:
        # 静态抓取遇到反爬，尝试Chrome
        chrome_result = fetch_with_chrome(url, timeout, wait_time, headless)
        if chrome_result['success']:
            return chrome_result

    return result


# ============ 批量抓取 ============

def fetch_batch(urls, use_chrome='auto', delay=1.0, save_dir=None, timeout=15, headless=True):
    """批量抓取多个URL

    Args:
        urls: URL列表
        use_chrome: Chrome模式
        delay: 请求间隔
        save_dir: 保存目录
        timeout: 超时时间
        headless: True=后台运行，False=显示窗口
    """

    results = []
    anti_crawl_count = 0

    for i, url in enumerate(urls):
        print(f"抓取 [{i+1}/{len(urls)}]: {url[:50]}...", file=sys.stderr)

        if delay > 0 and i > 0:
            time.sleep(delay)

        result = smart_fetch(url, use_chrome, timeout, headless=headless)

        if result.get('anti_crawl'):
            anti_crawl_count += 1

        # 保存文件
        if save_dir and result['success']:
            filepath = save_content(result, save_dir)
            result['local_file'] = filepath

        results.append(result)

    return results, anti_crawl_count


def save_content(result, save_dir):
    """保存内容到文件"""
    os.makedirs(save_dir, exist_ok=True)

    url_hash = hashlib.md5(result['url'].encode()).hexdigest()[:8]
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
    parser = argparse.ArgumentParser(description='网页内容抓取工具 - 复制Chrome配置版')
    parser.add_argument('urls', nargs='*', help='要抓取的URL')
    parser.add_argument('-c', '--chrome', choices=['auto', 'always', 'never'], default='auto',
                        help='Chrome模式: auto(自动判断), always(总是用Chrome), never(仅静态)')
    parser.add_argument('-w', '--wait', type=int, default=2, help='Chrome模式等待时间(秒)')
    parser.add_argument('-t', '--timeout', type=int, default=15, help='请求超时时间(秒)')
    parser.add_argument('-o', '--output', type=str, help='保存内容的目录')
    parser.add_argument('--delay', type=float, default=1.0, help='请求间隔延迟(秒)')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    parser.add_argument('--show-browser', action='store_true', help='显示浏览器窗口（用于处理验证码）')
    parser.add_argument('--close', action='store_true', help='关闭所有调试Chrome进程')

    args = parser.parse_args()

    # 关闭Chrome
    if args.close:
        close_chrome()
        # 额外清理
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/FI',
                          f'WINDOWTITLE eq *{CHROME_DEBUG_PORT}*'],
                          capture_output=True)
        print("Chrome调试进程已清理", file=sys.stderr)
        return

    # 检查是否有URL
    if not args.urls:
        parser.print_help()
        return

    save_dir = None
    if args.output:
        save_dir = os.path.expanduser(args.output)

    results, anti_crawl_count = fetch_batch(
        args.urls,
        use_chrome=args.chrome,
        delay=args.delay,
        save_dir=save_dir,
        timeout=args.timeout,
        headless=not args.show_browser
    )

    # 统计
    success_count = sum(1 for r in results if r['success'])
    total_length = sum(r.get('length', 0) for r in results if r['success'])

    output = {
        'total': len(results),
        'success': success_count,
        'failed': len(results) - success_count,
        'anti_crawl': anti_crawl_count,
        'total_length': total_length,
        'save_dir': save_dir,
        'results': results
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"\n抓取完成: {success_count}/{len(results)} 成功")
        if anti_crawl_count > 0:
            print(f"遇到反爬限制: {anti_crawl_count} 条")
        if save_dir:
            print(f"内容已保存到: {save_dir}")
        print()

        for i, r in enumerate(results, 1):
            status = "✓" if r['success'] else "✗"
            title = r.get('title', r['url'][:50])
            print(f"{i}. {status} {title}")
            if r['success']:
                print(f"   长度: {r.get('length', 0)} 字符 [{r.get('fetch_type', 'static')}]")
                if r.get('local_file'):
                    print(f"   文件: {r['local_file']}")
            else:
                print(f"   错误: {r.get('error', 'Unknown')}")


if __name__ == '__main__':
    main()