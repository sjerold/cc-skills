#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书导航模块 - 管理浏览器连接和登录检测
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LOGIN_WAIT_TIMEOUT, PAGE_LOAD_TIMEOUT
from chrome_helper import (
    CHROME_DEBUG_PORT,
    TEMP_CHROME_DIR,
    start_chrome,
    close_chrome,
)

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
            if not start_chrome(headless=self.headless):
                print("Chrome启动失败", file=sys.stderr)
                return False

            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp(
                f'http://127.0.0.1:{CHROME_DEBUG_PORT}'
            )

            self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()

            # 使用现有页面或创建新页面
            if self.context.pages:
                self.page = self.context.pages[0]
                # 先关闭其他页面避免干扰
                for other_page in self.context.pages[1:]:
                    try:
                        other_page.close()
                    except:
                        pass
            else:
                self.page = self.context.new_page()

            self.page.set_default_timeout(PAGE_LOAD_TIMEOUT * 1000)

            # 导航到目标URL
            navigate_url = target_url if target_url else self.domain
            print(f"正在打开: {navigate_url}", file=sys.stderr)

            # 执行导航
            try:
                self.page.goto(navigate_url, timeout=PAGE_LOAD_TIMEOUT * 1000, wait_until="domcontentloaded")
            except Exception as e:
                print(f"导航超时: {e}, 尝试继续...", file=sys.stderr)

            time.sleep(3)

            # 确认导航结果
            final_url = self.page.url
            print(f"导航后URL: {final_url}", file=sys.stderr)

            # 检查是否需要登录
            if self._check_login_required():
                return self._wait_for_login(timeout)
            else:
                print("已登录", file=sys.stderr)
                return True

        except Exception as e:
            print(f"连接Chrome失败: {e}", file=sys.stderr)
            return False

    def _wait_for_login(self, timeout: int) -> bool:
        """等待用户登录"""
        print("\n" + "=" * 50, file=sys.stderr)
        print("请在Chrome窗口中完成飞书登录...", file=sys.stderr)
        print(f"等待时间: {timeout}秒 ({timeout//60}分钟)", file=sys.stderr)
        print("=" * 50 + "\n", file=sys.stderr)

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
                        print("\n用户确认登录完成！", file=sys.stderr)
                        return True
                except:
                    pass

            # 每5秒检查登录状态
            if elapsed % 5 == 0:
                print(f"\r等待登录中... 已等待 {elapsed}秒, 剩余 {remaining}秒  ", end='', file=sys.stderr, flush=True)

                if not self._check_login_required():
                    print("\n\n登录成功！", file=sys.stderr)
                    time.sleep(2)
                    return True

        print("\n登录超时", file=sys.stderr)
        return False

    def _check_login_required(self) -> bool:
        """检查是否需要登录"""
        try:
            url = self.page.url.lower()
            content = self.page.content().lower()

            # 已登录特征
            logged_in = ['/drive/folder', '/docx/', '/wiki/', '/sheet/', '/space/']
            for indicator in logged_in:
                if indicator in url:
                    print(f"检测到已登录URL特征: {indicator}", file=sys.stderr)
                    return False

            # 登录特征
            login_indicators = ['/login', '/passport', '/sso', '/authenticate', '登录', '扫码登录']
            for indicator in login_indicators:
                if indicator in url or indicator in content:
                    print(f"检测到登录特征: {indicator}", file=sys.stderr)
                    return True

            # 检查用户头像
            try:
                user_menu = self.page.query_selector('[class*="avatar"], [class*="user"]')
                if user_menu:
                    print("检测到用户头像，判断为已登录", file=sys.stderr)
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

        print("已断开Chrome连接（Chrome保持运行，下次可复用登录状态）", file=sys.stderr)


if __name__ == '__main__':
    print("飞书导航模块 - 请通过 xianfeng_search.py 调用")