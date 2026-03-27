#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度搜索脚本 - 复制Chrome配置版
支持后台运行(headless)和自动关闭浏览器
"""

import sys
import json
import urllib.parse
import re
import io
import argparse
import os
import time
import hashlib
import shutil
import subprocess
import signal
import uuid
from datetime import datetime
from pathlib import Path

# 确保 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    import requests
except ImportError:
    print(json.dumps({'error': '请安装 requests: pip install requests'}, ensure_ascii=False))
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


# ============ 配置 ============

CHROME_DEBUG_PORT = 9223

# Chrome配置目录
if sys.platform == 'win32':
    CHROME_USER_DATA_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')
    TEMP_CHROME_DIR = os.path.join(os.environ['TEMP'], 'chrome-search-profile')
else:
    CHROME_USER_DATA_DIR = os.path.expanduser('~/.config/google-chrome')
    TEMP_CHROME_DIR = '/tmp/chrome-search-profile'

# 需要复制的目录
COPY_DIRS = ['Default', 'Profile 1', 'Profile 2']

# Chrome进程PID文件
CHROME_PID_FILE = os.path.join(TEMP_CHROME_DIR, '.chrome_pid')

# 默认保存目录
DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser('~'), 'Downloads', 'baidu_search')


def generate_session_id():
    """生成会话ID"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    short_uuid = uuid.uuid4().hex[:8]
    return f"{timestamp}_{short_uuid}"


def get_session_dir(base_dir=None, session_id=None):
    """获取会话目录

    Args:
        base_dir: 基础目录，默认为 ~/Downloads/baidu_search
        session_id: 会话ID，不提供则自动生成
    """
    if base_dir is None:
        base_dir = DEFAULT_OUTPUT_DIR

    if session_id is None:
        session_id = generate_session_id()

    session_dir = os.path.join(base_dir, session_id)
    os.makedirs(session_dir, exist_ok=True)

    return session_dir, session_id


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


def check_captcha(page, headless):
    """检测验证码"""
    indicators = ['wappass.baidu.com', 'captcha', '验证']

    try:
        url = page.url.lower()
        content = page.content().lower()

        is_captcha = any(i in url for i in indicators) or '百度安全验证' in content

        if is_captcha:
            if headless:
                print("\n检测到验证码，后台模式无法处理", file=sys.stderr)
                return False

            print("\n" + "=" * 50, file=sys.stderr)
            print("请在Chrome窗口中完成验证...", file=sys.stderr)
            print("=" * 50 + "\n", file=sys.stderr)

            start = time.time()
            while time.time() - start < 300:
                time.sleep(1)
                try:
                    if not any(i in page.url.lower() for i in indicators):
                        content = page.content().lower()
                        if '百度安全验证' not in content:
                            print("验证完成！", file=sys.stderr)
                            time.sleep(1)
                            return True
                except:
                    pass
            return False
    except:
        pass
    return True


def search(query, limit=50, headless=True):
    """执行搜索

    Args:
        query: 搜索关键词
        limit: 结果数量
        headless: True=后台运行，False=显示窗口
    """
    if not HAS_PLAYWRIGHT:
        print("请安装: pip install playwright", file=sys.stderr)
        return []

    if not start_chrome(headless=headless):
        return []

    results = []
    browser = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f'http://127.0.0.1:{CHROME_DEBUG_PORT}')
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()

            page.goto('https://www.baidu.com', timeout=30000)
            if not check_captcha(page, headless):
                return []

            for pagenum in range(1, (limit // 10) + 2):
                pn = (pagenum - 1) * 10
                url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}&pn={pn}"

                page.goto(url, timeout=30000)
                time.sleep(2)
                if not check_captcha(page, headless):
                    break

                try:
                    page.wait_for_selector('div.result', timeout=10000)
                except:
                    continue

                html = page.content()

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
                                # 计算质量分数
                                result['score'] = calculate_quality_score(result)
                                results.append(result)

                if len(results) >= limit:
                    break

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
    finally:
        # 通过Playwright关闭浏览器
        if browser:
            try:
                browser.close()
                print("Chrome已关闭", file=sys.stderr)
            except:
                # 如果Playwright关闭失败，使用系统方法
                close_chrome()

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


def calculate_quality_score(result):
    """根据URL和标题计算质量分数

    评分规则：
    - 官方文档/开源项目: python.org, github.com, gitee.com 等 × 2.5
    - 技术社区: stackoverflow, csdn, juejin, zhihu 等 × 1.4~2.3
    - 官方机构: edu.cn, gov.cn × 1.8
    - 企业官网: 主要企业域名 × 2.0
    - 新闻媒体: 主流新闻网站 × 1.5
    - 低质量: 贴吧、论坛灌水等 × 0.3~0.5
    """
    url = result.get('url', '').lower()
    title = result.get('title', '').lower()

    # 基础分
    base_score = 1.0

    # 官方文档/开源项目 (× 2.5)
    official_patterns = ['python.org', 'github.com', 'gitee.com', 'pypi.org',
                        'readthedocs', 'docs.', 'developer.', 'documentation']
    for pattern in official_patterns:
        if pattern in url:
            return base_score * 2.5

    # 官方机构 (× 1.8)
    gov_patterns = ['.gov.cn', '.edu.cn', 'gov.cn', 'edu.cn']
    for pattern in gov_patterns:
        if pattern in url:
            return base_score * 1.8

    # 技术社区 (× 1.4~2.3)
    tech_community = {
        'stackoverflow.com': 2.3,
        'csdn.net': 1.8,
        'juejin.cn': 1.9,
        'zhihu.com': 1.6,
        'segmentfault.com': 1.8,
        'infoq.cn': 2.0,
        'jb51.net': 1.4,
        'w3cschool': 1.7,
        'runoob.com': 1.7,
    }
    for domain, multiplier in tech_community.items():
        if domain in url:
            return base_score * multiplier

    # 企业官网 (× 2.0)
    enterprise_patterns = ['.com.cn', '官方网站', '官网']
    for pattern in enterprise_patterns:
        if pattern in url or pattern in title:
            return base_score * 2.0

    # 新闻媒体 (× 1.5)
    news_patterns = ['news.', 'xinwen', 'sina.com', 'qq.com', 'sohu.com',
                     '163.com', 'ifeng.com', 'people.com.cn', 'xinhua']
    for pattern in news_patterns:
        if pattern in url:
            return base_score * 1.5

    # 低质量内容 (× 0.3~0.5)
    low_quality = ['tieba.baidu.com', 'forum', 'bbs', '贴吧', '灌水']
    for pattern in low_quality:
        if pattern in url or pattern in title:
            return base_score * 0.3

    return base_score


def fetch_urls(urls, save_dir=None, delay=1.0, headless=True):
    """抓取网页 - 使用Playwright动态渲染

    Args:
        urls: URL列表
        save_dir: 保存目录
        delay: 请求间隔
        headless: True=后台运行，False=显示窗口
    """
    if not HAS_PLAYWRIGHT:
        print("Playwright未安装，使用静态抓取...", file=sys.stderr)
        return fetch_urls_static(urls, save_dir, delay)

    results = []
    browser = None

    try:
        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            page.set_default_timeout(30000)

            for i, url in enumerate(urls):
                print(f"抓取 [{i+1}/{len(urls)}]: {url[:50]}...", file=sys.stderr)

                if delay and i > 0:
                    time.sleep(delay)

                try:
                    # 访问页面
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(2)  # 等待JS渲染

                    # 等待网络空闲
                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        pass

                    # 检测反爬
                    html = page.content()
                    final_url = page.url

                    anti_patterns = ['百度安全验证', '安全验证', '验证码', 'captcha',
                                    'wappass.baidu.com', '请输入验证码', '访问过于频繁']
                    is_anti = any(p.lower() in html.lower() for p in anti_patterns)

                    if is_anti:
                        result = {
                            'success': False,
                            'error': '遇到反爬限制',
                            'url': url,
                            'anti_crawl': True
                        }
                    else:
                        # 解析内容
                        if HAS_BS4:
                            soup = BeautifulSoup(html, 'html.parser')
                            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe']):
                                tag.decompose()

                            title = soup.find('title').get_text(strip=True) if soup.find('title') else ''

                            # 提取正文
                            content_selectors = ['article', 'main', '.content', '.article', '.post',
                                               '.entry-content', '.post-content', '#content', 'body']
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
                            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                            title = title_match.group(1).strip() if title_match else ''
                            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                            text = re.sub(r'<[^>]+>', '\n', text)
                            content_text = re.sub(r'\n+', '\n', text).strip()

                        # 清理和截断
                        content_text = '\n'.join(line.strip() for line in content_text.split('\n') if line.strip())
                        if len(content_text) > 15000:
                            content_text = content_text[:15000] + '\n... (内容已截断)'

                        result = {
                            'success': True,
                            'title': title,
                            'content': content_text,
                            'url': final_url,
                            'original_url': url,
                            'length': len(content_text),
                            'fetch_type': 'playwright'
                        }

                        # 保存为Markdown文件
                        if save_dir:
                            os.makedirs(save_dir, exist_ok=True)
                            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:50]
                            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                            filepath = os.path.join(save_dir, f"{safe_title}_{url_hash}.md")
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(f"# {title}\n\n")
                                f.write(f"- **URL**: {final_url}\n")
                                f.write(f"- **原始URL**: {url}\n")
                                f.write(f"- **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                f.write(f"- **抓取方式**: playwright\n")
                                f.write(f"- **内容长度**: {len(content_text)} 字符\n\n")
                                f.write("---\n\n")
                                f.write("## 正文内容\n\n")
                                f.write(content_text)
                            result['file'] = filepath

                except Exception as e:
                    result = {'success': False, 'error': str(e), 'url': url}

                results.append(result)

    except Exception as e:
        print(f"Playwright错误: {e}", file=sys.stderr)
        return fetch_urls_static(urls, save_dir, delay)
    finally:
        if browser:
            try:
                browser.close()
            except:
                pass

    return results


def fetch_urls_static(urls, save_dir=None, delay=1.0):
    """静态抓取网页（备用方案）"""
    results = []

    for i, url in enumerate(urls):
        print(f"静态抓取 [{i+1}/{len(urls)}]: {url[:50]}...", file=sys.stderr)

        try:
            if delay and i > 0:
                time.sleep(delay)

            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0'}
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)

            if HAS_BS4:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for tag in soup(['script', 'style', 'nav', 'footer']):
                    tag.decompose()
                text = soup.get_text(separator='\n', strip=True)[:10000]
                title = soup.find('title').get_text(strip=True) if soup.find('title') else ''
            else:
                text = re.sub(r'<[^>]+>', ' ', resp.text)[:10000]
                title = ''

            result = {
                'success': True,
                'title': title,
                'content': text,
                'url': resp.url,
                'original_url': url,
                'length': len(text),
                'fetch_type': 'static'
            }

            # 保存为Markdown文件
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
                safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:50] if title else 'untitled'
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                filepath = os.path.join(save_dir, f"{safe_title}_{url_hash}.md")
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# {title}\n\n")
                    f.write(f"- **URL**: {resp.url}\n")
                    f.write(f"- **原始URL**: {url}\n")
                    f.write(f"- **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"- **抓取方式**: static\n")
                    f.write(f"- **内容长度**: {len(text)} 字符\n\n")
                    f.write("---\n\n")
                    f.write("## 正文内容\n\n")
                    f.write(text)
                result['file'] = filepath

            results.append(result)

        except Exception as e:
            results.append({'success': False, 'error': str(e), 'url': url})

    return results


def compile_results(query, results, fetched, save_dir, session_id):
    """整理抓取结果，生成最终Markdown报告

    Args:
        query: 搜索关键词
        results: 搜索结果列表
        fetched: 抓取结果列表
        save_dir: 保存目录
        session_id: 会话ID
    """
    if not save_dir:
        return None

    os.makedirs(save_dir, exist_ok=True)
    report_path = os.path.join(save_dir, f"搜索报告_{session_id}.md")

    with open(report_path, 'w', encoding='utf-8') as f:
        # 标题
        f.write(f"# 搜索报告：{query}\n\n")
        f.write(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"> 会话ID：{session_id}\n\n")

        # 搜索概况
        f.write("## 搜索概况\n\n")
        f.write(f"- **搜索关键词**: {query}\n")
        f.write(f"- **搜索结果数**: {len(results)} 条\n")
        fetched_success = sum(1 for r in fetched if r.get('success'))
        f.write(f"- **抓取成功数**: {fetched_success}/{len(fetched)} 条\n\n")

        # 参考链接
        f.write("## 参考链接\n\n")
        f.write("| 序号 | 标题 | URL | 质量分数 |\n")
        f.write("|------|------|-----|----------|\n")
        for i, r in enumerate(results[:30], 1):
            title = r.get('title', 'N/A')[:40]
            url = r.get('url', '')
            score = r.get('score', 1.0)
            f.write(f"| {i} | {title} | [链接]({url}) | {score:.2f} |\n")
        f.write("\n")

        # 抓取内容摘要
        f.write("## 抓取内容摘要\n\n")
        for i, r in enumerate(fetched, 1):
            if r.get('success'):
                title = r.get('title', '无标题')
                url = r.get('url', '')
                content_len = r.get('length', 0)
                fetch_type = r.get('fetch_type', 'unknown')
                filepath = r.get('file', '')

                f.write(f"### {i}. {title}\n\n")
                f.write(f"- **URL**: {url}\n")
                f.write(f"- **内容长度**: {content_len} 字符\n")
                f.write(f"- **抓取方式**: {fetch_type}\n")
                if filepath:
                    f.write(f"- **本地文件**: `{os.path.basename(filepath)}`\n")
                f.write("\n")

                # 内容预览（前500字符）
                content = r.get('content', '')
                if content:
                    preview = content[:500]
                    if len(content) > 500:
                        preview += '...'
                    f.write("**内容预览**:\n\n")
                    f.write("```\n")
                    f.write(preview)
                    f.write("\n```\n\n")

                f.write("---\n\n")

        # 数据来源
        f.write("## 数据来源\n\n")
        f.write("本次搜索数据来源于百度搜索，抓取时间为标注时间。\n\n")
        f.write("### 本地存档文件列表\n\n")
        for r in fetched:
            if r.get('file'):
                filepath = r['file']
                f.write(f"- [{os.path.basename(filepath)}]({os.path.basename(filepath)})\n")

    print(f"\n报告已生成: {report_path}", file=sys.stderr)
    return report_path


def read_all_md_files(save_dir):
    """读取目录下所有md文件内容

    Args:
        save_dir: 保存目录

    Returns:
        dict: {filename: content}
    """
    md_contents = {}

    if not save_dir or not os.path.exists(save_dir):
        return md_contents

    for filename in os.listdir(save_dir):
        if filename.endswith('.md') and not filename.startswith('搜索报告'):
            filepath = os.path.join(save_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    md_contents[filename] = f.read()
            except Exception as e:
                print(f"读取文件失败 {filename}: {e}", file=sys.stderr)

    return md_contents


def generate_summary(query, results, md_contents, save_dir, session_id):
    """生成搜索结果总结

    Args:
        query: 搜索关键词
        results: 搜索结果列表
        md_contents: 所有md文件内容
        save_dir: 保存目录
        session_id: 会话ID
    """
    summary_path = os.path.join(save_dir, f"搜索总结_{session_id}.md")

    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f"# 搜索总结：{query}\n\n")
        f.write(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"> 会话ID：{session_id}\n\n")

        # 统计信息
        f.write("## 统计信息\n\n")
        f.write(f"- **搜索结果**: {len(results)} 条\n")
        f.write(f"- **抓取文件**: {len(md_contents)} 个\n")

        # 计算总内容长度
        total_length = sum(len(content) for content in md_contents.values())
        f.write(f"- **总内容量**: {total_length:,} 字符\n\n")

        # 参考来源
        f.write("## 参考来源\n\n")
        for i, (filename, content) in enumerate(md_contents.items(), 1):
            # 提取标题（第一个#后面的内容）
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else filename
            f.write(f"{i}. {title} (`{filename}`)\n")
        f.write("\n")

        # 内容整合
        f.write("## 整合内容\n\n")
        f.write("---\n\n")

        for i, (filename, content) in enumerate(md_contents.items(), 1):
            # 提取标题
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else filename

            f.write(f"### 来源 {i}: {title}\n\n")

            # 提取正文内容（## 正文内容 之后的部分）
            content_match = re.search(r'## 正文内容\s*\n([\s\S]+)$', content)
            if content_match:
                body = content_match.group(1).strip()
                # 截断过长内容
                if len(body) > 3000:
                    body = body[:3000] + '\n\n... (内容已截断)'
                f.write(body)
            else:
                # 如果没有正文标记，使用原始内容
                f.write(content[:3000])

            f.write("\n\n---\n\n")

        # 关键发现（基于内容长度排序）
        f.write("## 主要内容概览\n\n")
        sorted_contents = sorted(md_contents.items(), key=lambda x: len(x[1]), reverse=True)

        for i, (filename, content) in enumerate(sorted_contents[:5], 1):
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else filename

            # 提取URL
            url_match = re.search(r'\*\*URL\*\*:\s*(.+)', content)
            url = url_match.group(1) if url_match else 'N/A'

            # 提取前200字符作为摘要
            content_match = re.search(r'## 正文内容\s*\n([\s\S]+)$', content)
            if content_match:
                abstract = content_match.group(1).strip()[:200]
            else:
                abstract = content[:200]

            f.write(f"### {i}. {title}\n\n")
            f.write(f"**来源**: {url}\n\n")
            f.write(f"**摘要**: {abstract}...\n\n")

    print(f"总结已生成: {summary_path}", file=sys.stderr)
    return summary_path


def main():
    parser = argparse.ArgumentParser(description='百度搜索增强版')
    parser.add_argument('query', nargs='*', help='搜索词')
    parser.add_argument('-n', '--limit', type=int, default=150, help='搜索结果数量 (默认150)')
    parser.add_argument('-t', '--top-percent', type=float, default=35, help='按分数筛选前N%%的结果进行抓取 (默认35%%)')
    parser.add_argument('--min-score', type=float, default=1.0, help='最低分数阈值 (默认1.0)')
    parser.add_argument('-o', '--output', help='保存目录 (默认 ~/Downloads/baidu_search/<session_id>)')
    parser.add_argument('--session-id', help='指定会话ID')
    parser.add_argument('--json', action='store_true', help='JSON输出')
    parser.add_argument('--show-browser', action='store_true', help='显示浏览器窗口（用于处理验证码）')
    parser.add_argument('--init', action='store_true', help='初始化Chrome（显示窗口）')
    parser.add_argument('--close', action='store_true', help='关闭所有调试Chrome进程')
    parser.add_argument('--no-summarize', action='store_true', help='不生成总结报告')

    args = parser.parse_args()

    # 关闭Chrome
    if args.close:
        close_chrome()
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/FI',
                          f'WINDOWTITLE eq *{CHROME_DEBUG_PORT}*'],
                          capture_output=True)
        print("Chrome调试进程已清理", file=sys.stderr)
        return

    # 初始化Chrome（显示窗口）
    if args.init:
        if start_chrome(headless=False):
            print("Chrome已启动，请在浏览器中完成验证码验证")
            print("验证完成后可使用 --close 关闭")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                close_chrome()
        return

    # 检查是否有搜索词
    if not args.query:
        parser.print_help()
        return

    query = ' '.join(args.query)

    # 创建会话目录
    session_dir, session_id = get_session_dir(args.output, args.session_id)
    print(f"搜索: {query}", file=sys.stderr)
    print(f"会话ID: {session_id}", file=sys.stderr)
    print(f"保存目录: {session_dir}", file=sys.stderr)

    # 搜索（默认后台运行）
    results = search(query, args.limit, headless=not args.show_browser)
    print(f"找到 {len(results)} 条结果", file=sys.stderr)

    if not results:
        print("未找到搜索结果", file=sys.stderr)
        return

    # 按分数筛选
    # 方法1: 按百分比筛选
    top_count = max(1, int(len(results) * args.top_percent / 100))
    # 方法2: 按分数阈值筛选
    filtered_results = [r for r in results if r.get('score', 1.0) >= args.min_score]
    # 取两者的交集或较小值
    fetch_count = min(top_count, len(filtered_results))
    fetch_count = max(1, fetch_count)  # 至少抓取1个

    print(f"筛选: 分数前{args.top_percent}% + 最低{args.min_score}分 = {fetch_count}条", file=sys.stderr)

    # 抓取网页
    urls = [r['url'] for r in results[:fetch_count]]
    fetched = fetch_urls(urls, session_dir, headless=not args.show_browser)
    success_count = sum(1 for r in fetched if r.get('success'))
    print(f"抓取成功: {success_count}/{len(urls)}", file=sys.stderr)

    # 生成搜索报告
    if success_count > 0:
        compile_results(query, results, fetched, session_dir, session_id)

        # 读取所有md文件并生成总结
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

        # 显示前20条结果
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


if __name__ == '__main__':
    main()