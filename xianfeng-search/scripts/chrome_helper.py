#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome辅助模块 - 使用common模块统一Chrome管理

改动：
- 使用common/chrome_manager（端口9222）
- 连接现有Chrome或启动新的调试实例
- 复用用户的登录状态
"""

import sys
import os

# 添加common模块路径
# 路径: xianfeng-search/scripts/chrome_helper.py -> plugins/common/scripts
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_SCRIPTS_DIR)
_PLUGINS_DIR = os.path.dirname(_PLUGIN_DIR)
COMMON_PATH = os.path.join(_PLUGINS_DIR, 'common', 'scripts')
sys.path.insert(0, COMMON_PATH)

# 导入common模块
try:
    from chrome_manager import (
        CHROME_DEBUG_PORT,
        get_browser,
        get_page,
        close_browser,
        is_chrome_debug_running,
        start_debug_chrome,
        kill_debug_chrome
    )
    HAS_CHROME_MANAGER = True
except ImportError as e:
    print(f"无法导入chrome_manager: {e}", file=sys.stderr)
    HAS_CHROME_MANAGER = False

    # 备用端口（如果common模块不可用）
    CHROME_DEBUG_PORT = 9225


def check_port_in_use(port):
    """检查端口是否在使用"""
    if HAS_CHROME_MANAGER:
        return is_chrome_debug_running()
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0


def start_chrome(headless=False):
    """启动Chrome调试模式

    Args:
        headless: True=后台运行，False=显示窗口
    """
    if HAS_CHROME_MANAGER:
        return start_debug_chrome(headless=headless)

    # 备用实现（如果common模块不可用）
    print("警告: 使用备用Chrome启动逻辑", file=sys.stderr)
    return False


def close_chrome():
    """关闭Chrome调试进程"""
    if HAS_CHROME_MANAGER:
        kill_debug_chrome()


if __name__ == '__main__':
    print("Chrome辅助模块 - 使用common模块统一管理")
    print(f"调试端口: {CHROME_DEBUG_PORT}")