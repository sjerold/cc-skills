#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome管理模块 - 异步版本

设计原则：
1. 所有插件共用同一个调试端口（9222）
2. 先检测是否已有调试Chrome运行，有则直接连接
3. 没有则启动新的调试模式Chrome
4. 连接时在现有浏览器开新tab，复用登录状态

使用方式：
    from chrome_manager import get_browser_async, get_page_async, close_browser_async

    playwright, browser = await get_browser_async()
    page = await get_page_async(browser, url='https://example.com')
    # ... 操作页面 ...
    await close_browser_async(browser, playwright, keep_running=True)
"""

import sys
import os
import socket
import subprocess
import shutil

# 统一调试端口（所有插件共用）
CHROME_DEBUG_PORT = 9222

# Chrome配置目录
if sys.platform == 'win32':
    CHROME_USER_DATA_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')
    TEMP_CHROME_DIR = os.path.join(os.environ['TEMP'], 'chrome-debug-profile')
else:
    CHROME_USER_DATA_DIR = os.path.expanduser('~/.config/google-chrome')
    TEMP_CHROME_DIR = '/tmp/chrome-debug-profile'

# 需要复制的配置目录
COPY_DIRS = ['Default', 'Profile 1', 'Profile 2']

# Chrome进程PID文件
CHROME_PID_FILE = os.path.join(os.environ.get('TEMP', '/tmp'), '.chrome_debug_pid')

# 尝试导入异步 Playwright
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("警告: Playwright未安装，请运行 pip install playwright && playwright install chromium", file=sys.stderr)


# ============ 同步辅助函数（启动Chrome进程） ============

def get_chrome_path():
    """获取Chrome可执行文件路径"""
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
    """检查端口是否在使用"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except:
        return False


def is_chrome_debug_running():
    """检查是否已有调试模式的Chrome运行"""
    return check_port_in_use(CHROME_DEBUG_PORT)


def is_user_chrome_running():
    """检查用户的Chrome是否正在运行"""
    try:
        result = subprocess.run(
            ['tasklist'],
            capture_output=True, text=True, timeout=5
        )
        chrome_count = result.stdout.lower().count('chrome.exe')
        return chrome_count > 0 and not is_chrome_debug_running()
    except:
        return False


def copy_chrome_profile():
    """复制Chrome配置到临时目录"""
    print("正在复制Chrome配置到临时目录...", file=sys.stderr)

    if os.path.exists(TEMP_CHROME_DIR):
        if os.path.exists(os.path.join(TEMP_CHROME_DIR, 'Default')):
            print(f"使用已有临时配置: {TEMP_CHROME_DIR}", file=sys.stderr)
            return TEMP_CHROME_DIR
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
                shutil.copytree(src, dst,
                    ignore=shutil.ignore_patterns(
                        'Cache*', 'GPUCache*', 'Code Cache*',
                        'DawnGraphiteCache*', 'DawnWebGPUCache*',
                        '*.lock', 'LOCK', 'lockfile',
                        'Session Storage', 'IndexedDB', 'File System',
                        'Service Worker', 'Web Applications'
                    ))
                copied_count += 1
                print(f"  复制 {dir_name} 成功", file=sys.stderr)
            except Exception as e:
                print(f"  警告: {dir_name} 复制失败: {e}", file=sys.stderr)

    if copied_count == 0:
        print("警告: 配置复制失败，将使用全新配置", file=sys.stderr)
    else:
        print(f"配置复制完成 (复制了 {copied_count} 个配置)", file=sys.stderr)

    return TEMP_CHROME_DIR


def start_debug_chrome(headless=False, wait_timeout=30):
    """启动调试模式的Chrome（同步）"""
    if is_chrome_debug_running():
        print(f"调试Chrome已运行（端口 {CHROME_DEBUG_PORT}）", file=sys.stderr)
        return True

    chrome_path = get_chrome_path()

    if is_user_chrome_running():
        print("用户Chrome正在运行，复制配置以共享session...", file=sys.stderr)
        user_data_dir = copy_chrome_profile()
    else:
        user_data_dir = CHROME_USER_DATA_DIR
        print(f"使用用户配置: {user_data_dir}", file=sys.stderr)

    cmd = [
        chrome_path,
        f"--remote-debugging-port={CHROME_DEBUG_PORT}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    if headless:
        cmd.append("--headless=new")
    else:
        cmd.extend([
            "--window-position=-8,-8",
            "--window-size=300,50",
        ])

    try:
        startupinfo = None
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0

        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 6  # SW_MINIMIZE

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=creationflags
        )

        with open(CHROME_PID_FILE, 'w') as f:
            f.write(str(proc.pid))

        import time
        for _ in range(wait_timeout * 2):
            time.sleep(0.5)
            if is_chrome_debug_running():
                print(f"Chrome已启动，PID: {proc.pid}", file=sys.stderr)
                return True

        print("Chrome启动超时", file=sys.stderr)
        return False

    except Exception as e:
        print(f"启动Chrome失败: {e}", file=sys.stderr)
        return False


def kill_debug_chrome():
    """强制关闭调试Chrome"""
    pid = None

    if os.path.exists(CHROME_PID_FILE):
        try:
            with open(CHROME_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.remove(CHROME_PID_FILE)
        except:
            pass

    if not pid and is_chrome_debug_running():
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

    import time
    time.sleep(1)

    if is_chrome_debug_running():
        print("Chrome端口仍在使用", file=sys.stderr)
    else:
        print("Chrome调试进程已清理", file=sys.stderr)


# ============ 异步核心函数 ============

async def get_browser_async(headless=False, auto_start=True):
    """获取浏览器实例（异步）

    Returns:
        (playwright, browser) 元组
    """
    if not HAS_PLAYWRIGHT:
        print("错误: Playwright未安装", file=sys.stderr)
        return None, None

    # 确保Chrome已启动（同步启动）
    if not is_chrome_debug_running():
        if auto_start:
            print(f"未发现调试Chrome，启动新的实例...", file=sys.stderr)
            if not start_debug_chrome(headless=headless):
                return None, None
        else:
            print(f"调试Chrome未运行（端口 {CHROME_DEBUG_PORT}）", file=sys.stderr)
            return None, None

    # 异步连接
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(
            f'http://127.0.0.1:{CHROME_DEBUG_PORT}'
        )
        print(f"已连接调试Chrome（端口 {CHROME_DEBUG_PORT}）", file=sys.stderr)
        return playwright, browser
    except Exception as e:
        print(f"连接Chrome失败: {e}", file=sys.stderr)
        return None, None


async def get_page_async(browser, url=None, timeout=30000):
    """获取页面对象（异步）

    Args:
        browser: Playwright Browser对象
        url: 可选，要导航到的URL
        timeout: 超时时间（毫秒）

    Returns:
        Playwright Page对象
    """
    if not browser:
        return None

    try:
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(timeout)

        if url:
            print(f"导航到: {url}", file=sys.stderr)
            await page.goto(url, timeout=timeout, wait_until="load")

        return page

    except Exception as e:
        print(f"获取页面失败: {e}", file=sys.stderr)
        return None


async def close_browser_async(browser, playwright=None, keep_running=True):
    """断开浏览器连接（异步）

    注意：不调用 browser.close() 和 playwright.stop()
    因为 CDP 连接断开时会产生 EPIPE 错误（Windows Node.js subprocess 问题）
    """
    # 连接外部Chrome，不需要清理
    if keep_running:
        print("断开Chrome连接（Chrome保持运行）", file=sys.stderr)
    # 不调用任何 close/stop 方法，避免 EPIPE


async def close_page_async(page):
    """关闭页面（异步）"""
    if page:
        try:
            await page.close()
        except:
            pass


# ============ 便捷函数 ============

async def quick_open_url_async(url, headless=False, timeout=30000):
    """快速打开URL（异步）

    Returns:
        (playwright, browser, page) 元组
    """
    playwright, browser = await get_browser_async(headless=headless)
    if not browser:
        return None, None, None

    page = await get_page_async(browser, url=url, timeout=timeout)
    return playwright, browser, page


# ============ 命令行入口 ============

if __name__ == '__main__':
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description='Chrome调试模式管理工具（异步版本）')
    parser.add_argument('--status', action='store_true', help='检查调试Chrome状态')
    parser.add_argument('--start', action='store_true', help='启动调试Chrome')
    parser.add_argument('--headless', action='store_true', help='后台运行')
    parser.add_argument('--kill', action='store_true', help='关闭调试Chrome')
    parser.add_argument('--test', action='store_true', help='测试连接')

    args = parser.parse_args()

    if args.status:
        if is_chrome_debug_running():
            print(f"调试Chrome运行中（端口 {CHROME_DEBUG_PORT}）")
        else:
            print(f"调试Chrome未运行（端口 {CHROME_DEBUG_PORT}）")

    elif args.start:
        start_debug_chrome(headless=args.headless)

    elif args.kill:
        kill_debug_chrome()

    elif args.test:
        async def test():
            playwright, browser, page = await quick_open_url_async('https://www.baidu.com', headless=args.headless)
            if page:
                print("测试成功，页面标题:", await page.title())
                await asyncio.sleep(3)
                await close_browser_async(browser, playwright, keep_running=True)
            else:
                print("测试失败")
        asyncio.run(test())

    else:
        parser.print_help()