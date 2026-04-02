#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome管理模块 - 统一的Chrome调试模式连接和启动

设计原则：
1. 所有插件共用同一个调试端口（9222）
2. 先检测是否已有调试Chrome运行，有则直接连接
3. 没有则启动新的调试模式Chrome
4. 如果用户Chrome正在运行（配置被锁定），复制配置到临时目录
5. 连接时在现有浏览器开新tab，复用登录状态

使用方式：
    from chrome_manager import get_browser, get_page, close_browser

    browser = get_browser()  # 获取或启动Chrome
    page = get_page(browser)  # 在现有浏览器开新tab
    # ... 操作页面 ...
    close_browser(browser, keep_running=True)  # 断开连接，保持Chrome运行
"""

import sys
import os
import time
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

# Chrome进程PID文件（记录我们启动的Chrome）
CHROME_PID_FILE = os.path.join(os.environ.get('TEMP', '/tmp'), '.chrome_debug_pid')

# 是否尝试导入Playwright
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("警告: Playwright未安装，请运行 pip install playwright", file=sys.stderr)

# 全局 Playwright 实例（避免 asyncio 循环冲突）
_global_playwright = None
_global_browser = None


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
    """检查是否已有调试模式的Chrome运行

    Returns:
        bool: True表示端口9222已有Chrome调试服务运行
    """
    return check_port_in_use(CHROME_DEBUG_PORT)


def is_user_chrome_running():
    """检查用户的Chrome是否正在运行（非调试模式）"""
    try:
        # 检查是否有Chrome进程但不是调试模式
        result = subprocess.run(
            ['tasklist'],
            capture_output=True, text=True, timeout=5
        )
        chrome_count = result.stdout.lower().count('chrome.exe')
        # 如果有Chrome进程但调试端口未开放，说明用户Chrome正在运行
        return chrome_count > 0 and not is_chrome_debug_running()
    except:
        return False


def copy_chrome_profile():
    """复制Chrome配置到临时目录

    当用户的Chrome正在运行时，配置目录被锁定，需要复制到临时目录。

    Returns:
        str: 临时配置目录路径
    """
    print("正在复制Chrome配置到临时目录...", file=sys.stderr)

    # 如果已有临时目录，检查是否可用
    if os.path.exists(TEMP_CHROME_DIR):
        # 检查是否有Default目录
        if os.path.exists(os.path.join(TEMP_CHROME_DIR, 'Default')):
            print(f"使用已有临时配置: {TEMP_CHROME_DIR}", file=sys.stderr)
            return TEMP_CHROME_DIR
        # 否则删除重建
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
                # 复制配置，跳过大文件和锁定文件
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
        print("警告: 配置复制失败，将使用全新配置（需要重新登录）", file=sys.stderr)
    else:
        print(f"配置复制完成 (复制了 {copied_count} 个配置)", file=sys.stderr)

    return TEMP_CHROME_DIR


def start_debug_chrome(headless=True, wait_timeout=30):
    """启动调试模式的Chrome

    Args:
        headless: 是否后台运行（无窗口），默认True
        wait_timeout: 等待启动的超时时间（秒）

    Returns:
        bool: 是否启动成功
    """
    if is_chrome_debug_running():
        print(f"调试Chrome已运行（端口 {CHROME_DEBUG_PORT}）", file=sys.stderr)
        return True

    chrome_path = get_chrome_path()

    # 决定使用哪个配置目录
    if is_user_chrome_running():
        # 用户Chrome正在运行，配置被锁定，复制配置到临时目录
        print("用户Chrome正在运行，复制配置以共享session...", file=sys.stderr)
        user_data_dir = copy_chrome_profile()
    else:
        # 用户Chrome未运行，直接使用原始配置
        user_data_dir = CHROME_USER_DATA_DIR
        print(f"使用用户配置: {user_data_dir}", file=sys.stderr)

    cmd = [
        chrome_path,
        f"--remote-debugging-port={CHROME_DEBUG_PORT}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    # headless 模式（后台运行）
    if headless:
        cmd.append("--headless=new")

    try:
        # 启动Chrome
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )

        # 保存PID
        with open(CHROME_PID_FILE, 'w') as f:
            f.write(str(proc.pid))

        # 等待端口可用
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


def get_browser(headless=True, auto_start=True):
    """获取浏览器实例

    逻辑：
    1. 检查端口9222是否有调试Chrome
    2. 有 → 连接现有Chrome（复用登录状态）
    3. 没有 → 启动新的调试Chrome（如果auto_start=True）

    Args:
        headless: 启动时是否后台运行（无窗口），默认True
        auto_start: 如果没有运行的Chrome，是否自动启动

    Returns:
        Playwright Browser对象，或None
    """
    if not HAS_PLAYWRIGHT:
        print("错误: Playwright未安装", file=sys.stderr)
        return None

    # 检查是否已有调试Chrome
    if not is_chrome_debug_running():
        if auto_start:
            print(f"未发现调试Chrome，启动新的实例...", file=sys.stderr)
            if not start_debug_chrome(headless=headless):
                return None
        else:
            print(f"调试Chrome未运行（端口 {CHROME_DEBUG_PORT}）", file=sys.stderr)
            return None

    # 连接现有Chrome（复用全局 Playwright 实例）
    global _global_playwright, _global_browser

    try:
        # 如果已有浏览器连接且仍然有效，直接返回
        if _global_browser is not None:
            try:
                # 测试连接是否有效
                _global_browser.contexts
                print(f"复用已有Chrome连接（端口 {CHROME_DEBUG_PORT}）", file=sys.stderr)
                return _global_browser
            except:
                # 连接已失效，重新连接
                _global_browser = None
                if _global_playwright:
                    try:
                        _global_playwright.stop()
                    except:
                        pass
                    _global_playwright = None

        # 启动新的 Playwright 实例
        _global_playwright = sync_playwright().start()
        _global_browser = _global_playwright.chromium.connect_over_cdp(
            f'http://127.0.0.1:{CHROME_DEBUG_PORT}'
        )
        print(f"已连接调试Chrome（端口 {CHROME_DEBUG_PORT}）", file=sys.stderr)
        return _global_browser
    except Exception as e:
        print(f"连接Chrome失败: {e}", file=sys.stderr)
        return None


def get_page(browser, url=None, timeout=30000):
    """获取页面对象，在现有浏览器中开新tab

    Args:
        browser: Playwright Browser对象
        url: 可选，要导航到的URL
        timeout: 页面操作超时时间（毫秒）

    Returns:
        Playwright Page对象
    """
    if not browser:
        return None

    try:
        # 使用第一个context（用户的浏览器context）
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        # 创建新页面（在现有浏览器中开新tab）
        page = context.new_page()
        page.set_default_timeout(timeout)

        if url:
            print(f"导航到: {url}", file=sys.stderr)
            page.goto(url, timeout=timeout, wait_until="domcontentloaded")

        return page

    except Exception as e:
        print(f"获取页面失败: {e}", file=sys.stderr)
        return None


def get_existing_page(browser, index=0):
    """获取现有的页面对象（不创建新tab）

    Args:
        browser: Playwright Browser对象
        index: 页面索引，0表示第一个页面

    Returns:
        Playwright Page对象
    """
    if not browser:
        return None

    try:
        context = browser.contexts[0] if browser.contexts else None
        if context and len(context.pages) > index:
            return context.pages[index]
        return None
    except:
        return None


def close_browser(browser, keep_running=True):
    """断开浏览器连接

    Args:
        browser: Playwright Browser对象
        keep_running: True=保持Chrome运行以便下次复用，False=关闭Chrome
    """
    try:
        if browser:
            if keep_running:
                # 只断开连接，不关闭浏览器
                print("断开Chrome连接（Chrome保持运行，下次可复用登录状态）", file=sys.stderr)
            else:
                # 关闭浏览器
                browser.close()
                print("Chrome已关闭", file=sys.stderr)
    except:
        pass


def kill_debug_chrome():
    """强制关闭调试Chrome（如果是我们启动的）"""
    pid = None

    # 读取保存的PID
    if os.path.exists(CHROME_PID_FILE):
        try:
            with open(CHROME_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.remove(CHROME_PID_FILE)
        except:
            pass

    # 如果没有PID文件，从端口获取
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

    time.sleep(1)

    if is_chrome_debug_running():
        print("Chrome端口仍在使用", file=sys.stderr)
    else:
        print("Chrome调试进程已清理", file=sys.stderr)


# ============ 便捷函数 ============

def quick_open_url(url, headless=False, timeout=30000):
    """快速打开URL的便捷函数

    自动处理：获取浏览器 → 创建页面 → 导航 → 返回页面
    使用后需要手动调用 close_browser()

    Args:
        url: 要打开的URL
        headless: 是否后台运行
        timeout: 超时时间

    Returns:
        (browser, page) 元组
    """
    browser = get_browser(headless=headless)
    if not browser:
        return None, None

    page = get_page(browser, url=url, timeout=timeout)
    return browser, page


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Chrome调试模式管理工具')
    parser.add_argument('--status', action='store_true', help='检查调试Chrome状态')
    parser.add_argument('--start', action='store_true', help='启动调试Chrome')
    parser.add_argument('--headless', action='store_true', help='后台运行（配合--start）')
    parser.add_argument('--kill', action='store_true', help='关闭调试Chrome')
    parser.add_argument('--test', action='store_true', help='测试连接并打开一个页面')

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
        browser, page = quick_open_url('https://www.baidu.com', headless=args.headless)
        if page:
            print("测试成功，页面标题:", page.title())
            time.sleep(3)
            close_browser(browser, keep_running=True)
        else:
            print("测试失败")

    else:
        parser.print_help()