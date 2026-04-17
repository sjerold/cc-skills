#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书导航模块 - 使用common模块统一Chrome管理

改动：
- 使用common/chrome_manager连接现有Chrome
- 在现有浏览器开新tab
- 复用用户的登录状态
"""

import sys
import os
import time

# 添加脚本目录和common模块路径
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
_PLUGIN_DIR = os.path.dirname(_SCRIPTS_DIR)
_PLUGINS_DIR = os.path.dirname(_PLUGIN_DIR)
COMMON_PATH = os.path.join(_PLUGINS_DIR, 'common', 'scripts')
sys.path.insert(0, COMMON_PATH)

from utils import log
from config import LOGIN_WAIT_TIMEOUT, PAGE_LOAD_TIMEOUT

# 导入common模块
try:
    from chrome_manager import (
        CHROME_DEBUG_PORT,
        get_browser,
        get_page,
        close_browser,
        is_chrome_debug_running,
        start_debug_chrome,
        get_existing_page
    )
    HAS_CHROME_MANAGER = True
except ImportError as e:
    log(f"无法导入chrome_manager: {e}")
    HAS_CHROME_MANAGER = False
    # 备用：使用本地chrome_helper
    from chrome_helper import CHROME_DEBUG_PORT, start_chrome, close_chrome

# 尝试导入Playwright
HAS_PLAYWRIGHT = False
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    pass


class FeishuNavigator:
    """飞书导航器 - 连接Chrome并管理登录"""

    def __init__(self, domain: str, headless: bool = False):
        """
        初始化导航器

        Args:
            domain: 飞书域名 (如: https://your-feishu.example.com)
            headless: 是否后台运行
        """
        self.domain = domain.rstrip('/')
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.headless = headless

    def open_and_wait_login(self, target_url: str = None, timeout: int = LOGIN_WAIT_TIMEOUT) -> bool:
        """
        启动Chrome并等待登录

        Args:
            target_url: 目标URL（可选）
            timeout: 登录等待超时（秒）

        Returns:
            是否登录成功
        """
        if not HAS_PLAYWRIGHT:
            raise RuntimeError("Playwright未安装。请运行: pip install playwright")

        try:
            # 使用common模块获取浏览器（返回 playwright, browser 元组）
            log(f"  → 正在获取Chrome实例...")
            if HAS_CHROME_MANAGER:
                self.playwright, self.browser = get_browser(headless=self.headless)
                if not self.browser:
                    log(f"  ✗ 无法连接Chrome")
                    return False
            else:
                # 备用逻辑
                if not start_chrome(headless=self.headless):
                    log(f"  ✗ Chrome启动失败")
                    return False

                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.connect_over_cdp(
                    f'http://127.0.0.1:{CHROME_DEBUG_PORT}'
                )

            log(f"  ✓ Chrome CDP连接成功")
            self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()

            # 使用现有页面（复用已打开的tab，避免创建新tab）
            log(f"  → 获取页面...")
            if HAS_CHROME_MANAGER:
                self.page = get_existing_page(self.browser, timeout=PAGE_LOAD_TIMEOUT * 1000)
            else:
                if self.context.pages:
                    self.page = self.context.pages[0]
                    # 关闭其他页面避免干扰
                    for other_page in self.context.pages[1:]:
                        try:
                            other_page.close()
                        except:
                            pass
                else:
                    self.page = self.context.new_page()
                    self.page.set_default_timeout(PAGE_LOAD_TIMEOUT * 1000)

            log(f"  ✓ 获取页面成功")

            # 导航到目标URL
            navigate_url = target_url if target_url else self.domain
            log(f"  → 导航到: {navigate_url[:60]}...")

            try:
                self.page.goto(navigate_url, timeout=PAGE_LOAD_TIMEOUT * 1000, wait_until="domcontentloaded")
            except Exception as e:
                log(f"  ! 导航超时: {e}, 尝试继续...")

            time.sleep(3)

            # 检查是否被重定向，确保到达目标URL
            final_url = self.page.url
            log(f"  → 当前URL: {final_url[:60]}...")

            # 如果URL不包含目标folder_id，强制重新导航（最多3次）
            if target_url and '/folder/' in target_url:
                target_folder_id = target_url.split('/folder/')[-1].split('?')[0]
                retry_count = 0
                while target_folder_id not in final_url and retry_count < 3:
                    log(f"  ! 被重定向，重新导航... (尝试 {retry_count + 1}/3)")
                    try:
                        self.page.goto(navigate_url, timeout=PAGE_LOAD_TIMEOUT * 1000, wait_until="networkidle")
                    except:
                        pass
                    time.sleep(2)
                    final_url = self.page.url
                    log(f"  → 重新导航后URL: {final_url[:60]}...")
                    retry_count += 1

            # 检查是否需要登录
            if self._check_login_required():
                log(f"  → 需要登录，等待用户操作...")
                return self._wait_for_login(timeout)
            else:
                log(f"  ✓ 已登录")
                return True

        except Exception as e:
            log(f"  ✗ 连接Chrome失败: {e}")
            return False

    def _wait_for_login(self, timeout: int) -> bool:
        """等待用户登录"""
        log("\n" + "=" * 50)
        log("请在Chrome窗口中完成飞书登录...")
        log(f"等待时间: {timeout}秒 ({timeout//60}分钟)")
        log("=" * 50 + "\n")

        start_time = time.time()

        while time.time() - start_time < timeout:
            time.sleep(1)
            elapsed = int(time.time() - start_time)
            remaining = timeout - elapsed

            # Windows: 检测键盘输入
            if sys.platform == 'win32':
                try:
                    import msvcrt
                    if msvcrt.kbhit():
                        msvcrt.getch()
                        log("\n用户确认登录完成！")
                        return True
                except:
                    pass

            # 每5秒检查登录状态
            if elapsed % 5 == 0:
                print(f"\r等待登录中... 已等待 {elapsed}秒, 剩余 {remaining}秒  ", end='', file=sys.stderr, flush=True)

                if not self._check_login_required():
                    log("\n\n登录成功！")
                    time.sleep(2)
                    return True

        log("\n登录超时")
        return False

    def _check_login_required(self) -> bool:
        """检查是否需要登录"""
        try:
            url = self.page.url.lower()
            content = self.page.content().lower()

            # 已登录特征
            logged_in = ['/drive/folder', '/docx/', '/wiki/', '/sheet/', '/sheets/', '/space/']
            for indicator in logged_in:
                if indicator in url:
                    log(f"检测到已登录URL特征: {indicator}")
                    return False

            # 登录特征
            login_indicators = ['/login', '/passport', '/sso', '/authenticate', '登录', '扫码登录']
            for indicator in login_indicators:
                if indicator in url or indicator in content:
                    log(f"检测到登录特征: {indicator}")
                    return True

            # 检查用户头像
            try:
                user_menu = self.page.query_selector('[class*="avatar"], [class*="user"]')
                if user_menu:
                    log("检测到用户头像，判断为已登录")
                    return False
            except:
                pass

            return True
        except:
            return True

    def get_page(self):
        """获取当前页面对象"""
        return self.page

    def get_current_url(self) -> str:
        """获取当前URL"""
        return self.page.url if self.page else ""

    def close(self):
        """断开Chrome连接（保持Chrome运行以复用登录session）"""
        if HAS_CHROME_MANAGER:
            close_browser(self.browser, self.playwright, keep_running=True)
        else:
            try:
                if self.browser:
                    self.browser = None
            except:
                pass

            try:
                if self.playwright:
                    self.playwright.stop()
            except:
                pass

            log("已断开Chrome连接（Chrome保持运行，下次可复用登录状态）")


if __name__ == '__main__':
    print("飞书导航模块 - 使用common模块统一管理")