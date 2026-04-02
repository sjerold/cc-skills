#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome辅助模块 - 启动和管理Chrome实例
"""

import sys
import os
import time
import socket
import shutil
import subprocess


# Chrome调试端口（独立端口，避免与其他插件冲突）
CHROME_DEBUG_PORT = 9225

# Chrome配置目录
if sys.platform == 'win32':
    CHROME_USER_DATA_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')
    TEMP_CHROME_DIR = os.path.join(os.environ['TEMP'], 'chrome-xianfeng-profile')
else:
    CHROME_USER_DATA_DIR = os.path.expanduser('~/.config/google-chrome')
    TEMP_CHROME_DIR = '/tmp/chrome-xianfeng-profile'

# 需要复制的Chrome Profile目录
COPY_DIRS = ['Default', 'Profile 1', 'Profile 2']

# Chrome进程PID文件
CHROME_PID_FILE = os.path.join(TEMP_CHROME_DIR, '.chrome_pid')


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
    """检查端口是否在使用"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0


def copy_chrome_profile():
    """复制Chrome配置到临时目录（仅在目录不存在时复制）"""
    if os.path.exists(TEMP_CHROME_DIR) and os.path.exists(os.path.join(TEMP_CHROME_DIR, 'Default')):
        print(f"使用已有Chrome配置: {TEMP_CHROME_DIR}", file=sys.stderr)
        return TEMP_CHROME_DIR

    print("正在复制Chrome配置...", file=sys.stderr)
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
                        'Session Storage', 'IndexedDB', 'File System'
                    ))
                copied_count += 1
                print(f"  复制 {dir_name} 成功", file=sys.stderr)
            except Exception as e:
                print(f"  警告: {dir_name} 部分文件复制失败: {e}", file=sys.stderr)

    if copied_count == 0:
        print("配置复制失败，将使用全新配置（需要重新登录）", file=sys.stderr)
    else:
        print(f"配置复制完成 (复制了 {copied_count} 个配置)", file=sys.stderr)
    return TEMP_CHROME_DIR


def start_chrome(headless=False):
    """启动Chrome调试模式

    Args:
        headless: True=后台运行，False=显示窗口
    """
    if check_port_in_use(CHROME_DEBUG_PORT):
        print(f"Chrome调试端口 {CHROME_DEBUG_PORT} 已可用，直接连接", file=sys.stderr)
        return True

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
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )

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

    if os.path.exists(CHROME_PID_FILE):
        try:
            with open(CHROME_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.remove(CHROME_PID_FILE)
        except:
            pass

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

    time.sleep(1)

    if check_port_in_use(CHROME_DEBUG_PORT):
        print("Chrome端口仍在使用", file=sys.stderr)
    else:
        print("Chrome调试进程已清理", file=sys.stderr)


if __name__ == '__main__':
    print("Chrome辅助模块 - 请通过 feishu_navigator.py 调用")