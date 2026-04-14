#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目录扫描模块 v2 - 遍历飞书知识库/文件夹目录结构
支持：
- 扫描当前文件夹
- 递归扫描子文件夹
- 增量缓存
"""

import os
import sys
import time
import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Callable, Tuple

# 添加脚本目录和common模块路径
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
_PLUGIN_DIR = os.path.dirname(_SCRIPTS_DIR)
_PLUGINS_DIR = os.path.dirname(_PLUGIN_DIR)
COMMON_PATH = os.path.join(_PLUGINS_DIR, 'common', 'scripts')
sys.path.insert(0, COMMON_PATH)

from utils import log

from config import (
    PAGE_LOAD_TIMEOUT,
    SCROLL_WAIT_TIME,
    SCAN_EXCLUDE_PATTERNS,
)
from cache_manager import build_folder_entry, find_folder_info_from_parent_cache


class DirectoryScanner:
    """飞书目录扫描器"""

    def __init__(self, navigator):
        """
        初始化扫描器

        Args:
            navigator: FeishuNavigator实例
        """
        self.navigator = navigator
        self.page = navigator.get_page()
        self.scanned_count = 0
        self.folder_count = 0

    def scan_current_folder(self, folder_id: str = None, progress_callback: Callable = None) -> Dict:
        """
        扫描当前文件夹（不递归子文件夹）

        Args:
            folder_id: 文件夹ID（用于缓存标识）
            progress_callback: 进度回调函数

        Returns:
            文件夹缓存数据
        """
        log(f"  → 开始扫描文件夹...")

        if not folder_id:
            # 从URL提取文件夹ID
            url = self.page.url
            match = re.search(r'/drive/folder/([^/?]+)', url)
            folder_id = match.group(1) if match else 'unknown'

        try:
            # 等待页面加载并确认URL正确
            time.sleep(3)

            # 检查当前URL，等待稳定
            current_url = self.page.url
            expected_folder_id = folder_id

            log(f"    当前URL: {current_url[:60]}...")

            # 如果URL不包含预期的folder_id，尝试等待
            if expected_folder_id and expected_folder_id not in current_url:
                log(f"    ! URL不匹配，等待页面稳定...")
                for i in range(10):
                    time.sleep(1)
                    current_url = self.page.url
                    if expected_folder_id in current_url:
                        log(f"    ✓ 页面已稳定")
                        break
                    log(f"      等待中... ({i+1}/10)")

            # 尝试通过API拦截获取文件列表
            log(f"    → 尝试API拦截获取文件列表...")
            api_result = self._try_api_intercept(folder_id)

            # 如果API获取成功，优先使用API结果
            if api_result and (api_result.get('docs') or api_result.get('subfolders')):
                log(f"    ✓ API获取成功，使用API结果")
                docs = api_result.get('docs', [])
                api_subfolders = api_result.get('subfolders', [])

                # 获取当前文件夹名称
                folder_name = self._get_current_folder_name()
                log(f"    文件夹名称: {folder_name}")

                folder_info = find_folder_info_from_parent_cache(folder_id)
                if folder_info.get('folder_path'):
                    folder_path = folder_info['folder_path']
                else:
                    folder_path = folder_name

                log(f"    完整路径: {folder_path}")

                last_modified = self._get_folder_last_modified()
                if last_modified:
                    log(f"    最后修改: {last_modified}")

                children = {}
                for sf in api_subfolders:
                    children[sf['id']] = {
                        'folder_id': sf['id'],
                        'folder_name': sf['name'],
                        'folder_path': f"{folder_path}/{sf['name']}",
                        'docs': [],
                        'children': {},
                        'doc_count': 0,
                        'child_count': 0,
                        'last_modified': None,
                    }

                cache_entry = build_folder_entry(
                    folder_id=folder_id,
                    folder_name=folder_name,
                    folder_path=folder_path,
                    docs=docs,
                    children=children,
                    last_modified=last_modified
                )

                log(f"  ✓ 扫描完成(API): {len(docs)} 个文档, {len(api_subfolders)} 个子文件夹")
                return cache_entry

            # API获取失败，使用DOM扫描方式
            log(f"    → API获取失败，使用DOM扫描方式")

            # 尝试触发虚拟列表渲染
            log(f"    → 触发列表渲染...")
            self._trigger_list_render()

            # 额外等待渲染完成
            time.sleep(3)

            # 再次检查当前URL（防止被重定向）
            current_url = self.page.url
            log(f"    扫描前URL: {current_url[:60]}...")

            # 获取当前文件夹名称
            folder_name = self._get_current_folder_name()
            log(f"    文件夹名称: {folder_name}")

            # 从父目录缓存中获取完整路径（优先使用）
            folder_info = find_folder_info_from_parent_cache(folder_id)
            if folder_info.get('folder_path'):
                folder_path = folder_info['folder_path']
            else:
                folder_path = folder_name

            log(f"    完整路径: {folder_path}")

            # 获取文件夹最后修改时间
            last_modified = self._get_folder_last_modified()
            if last_modified:
                log(f"    最后修改: {last_modified}")

            # 尝试从文件列表扫描
            log(f"    → 扫描文件列表...")
            docs = self._scan_file_list(progress_callback)
            log(f"    ✓ 发现 {len(docs)} 个文档")

            # 尝试获取子文件夹
            log(f"    → 扫描子文件夹...")
            subfolders = self._scan_subfolders()
            log(f"    ✓ 发现 {len(subfolders)} 个子文件夹")

            children = {}

            for sf in subfolders:
                children[sf['id']] = {
                    'folder_id': sf['id'],
                    'folder_name': sf['name'],
                    'folder_path': f"{folder_path}/{sf['name']}",
                    'docs': [],
                    'children': {},
                    'doc_count': 0,
                    'child_count': 0,
                    'last_modified': sf.get('last_modified'),
                }

            # 构建缓存条目
            cache_entry = build_folder_entry(
                folder_id=folder_id,
                folder_name=folder_name,
                folder_path=folder_path,
                docs=docs,
                children=children,
                last_modified=last_modified
            )

            log(f"  ✓ 扫描完成: {len(docs)} 个文档, {len(subfolders)} 个子文件夹")

            return cache_entry

        except Exception as e:
            log(f"  ✗ 扫描失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _trigger_list_render(self):
        """尝试触发虚拟列表渲染 - 使用多种策略确保内容加载"""
        try:
            # 策略0: 刷新页面重新触发渲染（解决页面状态问题）
            log("    → 刷新页面触发重新渲染...")
            try:
                self.page.reload(wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                log("    ✓ 页面刷新完成")
            except Exception as e:
                log(f"    ! 刷新失败: {e}")

            # 等待页面稳定
            log("    → 等待页面加载...")
            time.sleep(3)

            # 等待网络空闲
            try:
                self.page.wait_for_load_state("networkidle", timeout=20000)
                log("    ✓ 网络空闲")
            except:
                log("    ! 网络等待超时，继续执行")

            # 策略1: 悬停触发 - 飞书虚拟列表可能需要鼠标悬停才能渲染
            log("    → 尝试悬停触发...")
            try:
                # 找到主内容区域并悬停
                main_area = self.page.query_selector('.sc-gSQGeZ, .sc-jgrIVw, .main__content')
                if main_area:
                    main_area.hover(timeout=3000)
                    time.sleep(2)
                    log("    ✓ 悬停触发完成")
            except Exception as e:
                log(f"    ! 悬停触发失败: {e}")

            # 策略2: 多次滚动触发虚拟列表渲染
            scroll_selectors = [
                '.sc-gSQGeZ',           # 主滚动容器
                '.sc-jgrIVw',           # app-main
                '.main__content',
            ]

            for selector in scroll_selectors:
                try:
                    scroll_area = self.page.query_selector(selector)
                    if scroll_area:
                        log(f"    → 滚动触发: {selector}")
                        # 多次滚动，确保触发所有区域的渲染
                        for i in range(5):
                            # 滚动到底部
                            scroll_area.evaluate('el => { el.scrollTop = el.scrollHeight; }')
                            time.sleep(1)
                            # 滚动到中间
                            scroll_area.evaluate('el => { el.scrollTop = el.scrollHeight / 2; }')
                            time.sleep(0.5)
                            # 滚动到顶部
                            scroll_area.evaluate('el => { el.scrollTop = 0; }')
                            time.sleep(0.5)
                        log(f"    ✓ 滚动完成")
                        break
                except:
                    continue

            # 策略3: 按键触发焦点和渲染
            log("    → 尝试按键触发...")
            self.page.keyboard.press('Tab')
            time.sleep(0.5)
            self.page.keyboard.press('Tab')
            time.sleep(0.5)
            # 多次按方向键触发渲染
            for i in range(5):
                self.page.keyboard.press('ArrowDown')
                time.sleep(0.3)
            self.page.keyboard.press('ArrowUp')
            time.sleep(0.3)
            log("    ✓ 按键触发完成")

            # 策略4: 点击文件列表区域触发
            file_list_selectors = [
                '.explorer-file-list-virtualized__li',
                '[role="list"]',
                '[data-e2e="file-list"]',
                '.file-list-container',
                '.sc-gSQGeZ',           # 主内容区域
            ]

            clicked = False
            for selector in file_list_selectors:
                try:
                    elem = self.page.query_selector(selector)
                    if elem:
                        # 点击区域中心位置
                        box = elem.bounding_box()
                        if box:
                            # 点击区域中间位置（避免点击到具体元素）
                            self.page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                            time.sleep(1)
                            log(f"    点击区域: {selector}")
                            clicked = True
                            break
                except:
                    continue

            if not clicked:
                log("    未找到文件列表区域，跳过点击")

            # 策略5: 等待虚拟列表渲染完成（最长30秒）
            log("    → 等待虚拟列表渲染...")
            max_wait = 30
            for i in range(max_wait):
                # 检查placeholder是否消失
                placeholder = self.page.query_selector('[class*="placeholder"]')
                if not placeholder:
                    log("    ✓ placeholder消失")

                # 检查文档和文件夹链接数量
                doc_links = self.page.query_selector_all('a[href*="/docx/"]')
                folder_links = self.page.query_selector_all('a[href*="/folder/"]')

                # 过滤掉面包屑中的链接
                breadcrumb = self.page.query_selector('[class*="breadcrumb"]')
                breadcrumb_links = set()
                if breadcrumb:
                    breadcrumb_links = set(breadcrumb.query_selector_all('a'))

                actual_docs = [l for l in doc_links if l not in breadcrumb_links]
                actual_folders = [l for l in folder_links if l not in breadcrumb_links]

                total = len(actual_docs) + len(actual_folders)

                if total > 0:
                    log(f"    ✓ 渲染完成: {len(actual_docs)} 个文档, {len(actual_folders)} 个文件夹")
                    break

                if i % 5 == 0:
                    log(f"      等待中... ({i+1}/{max_wait})")
                    # 如果等待中还没有内容，再次尝试滚动
                    try:
                        scroll_area = self.page.query_selector('.sc-gSQGeZ')
                        if scroll_area:
                            scroll_area.evaluate('el => { el.scrollTop = el.scrollHeight; }')
                    except:
                        pass

                time.sleep(1)

            # 最终状态检查
            doc_links = self.page.query_selector_all('a[href*="/docx/"]')
            folder_links = self.page.query_selector_all('a[href*="/folder/"]')
            log(f"    最终检测: {len(doc_links)} 个文档链接, {len(folder_links)} 个文件夹链接")

        except Exception as e:
            log(f"触发渲染失败: {e}")

    def _get_folder_last_modified(self) -> Optional[str]:
        """获取文件夹最后修改时间"""
        try:
            # 尝试从页面获取修改时间
            # 飞书可能显示"修改于 X天前" 或 具体日期
            time_selectors = [
                '[class*="modify"]',
                '[class*="update"]',
                '[class*="time"]',
                '.last-modified',
            ]

            for selector in time_selectors:
                try:
                    elem = self.page.query_selector(selector)
                    if elem:
                        text = elem.inner_text().strip()
                        if text and ('修改' in text or '更新' in text or '-' in text):
                            return text
                except:
                    continue

            # 尝试从URL或页面元数据获取
            # 使用当前时间作为备选
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        except:
            return None

    def _get_current_folder_name(self) -> str:
        """获取当前文件夹名称"""
        # 方法1: 从面包屑导航获取最后一项（当前文件夹）
        # 面包屑结构通常是: 我的空间 > 文件夹1 > 文件夹2 > 当前文件夹
        try:
            # 尝试多种面包屑选择器
            breadcrumb_selectors = [
                '.breadcrumb-item',
                '.nav-path-item',
                '[class*="breadcrumb-item"]',
                '.ant-breadcrumb-link',
            ]

            for selector in breadcrumb_selectors:
                items = self.page.query_selector_all(selector)
                if items and len(items) > 0:
                    # 取最后一个非空的项
                    for item in reversed(items):
                        name = item.inner_text().strip()
                        # 过滤掉导航符号和空值
                        if name and name not in ['/', '>', '»', '›', '', 'Home', '我的空间']:
                            log(f"    从面包屑获取文件夹名: {name}")
                            return name
        except:
            pass

        # 方法2: 从页面标题区域获取
        try:
            # 文档标题通常在特定位置
            title_selectors = [
                '.drive-header-title',
                '.folder-title',
                '.current-folder-name',
                'h1.title',
                '[class*="title-text"]',
            ]

            for selector in title_selectors:
                elem = self.page.query_selector(selector)
                if elem:
                    name = elem.inner_text().strip()
                    if name and len(name) < 100 and name not in ['Home', '我的空间', '主页']:
                        log(f"    从标题获取文件夹名: {name}")
                        return name
        except:
            pass

        # 方法3: 从URL提取作为备选
        url = self.page.url
        if '/folder/' in url:
            folder_id = url.split('/folder/')[-1].split('?')[0][:8]
            log(f"    从URL获取文件夹名: 文件夹_{folder_id}")
            return f"文件夹_{folder_id}"

        log(f"    无法获取文件夹名，使用默认值")
        return "未命名文件夹"

    def _scan_file_list(self, progress_callback: Callable = None) -> List[Dict]:
        """
        扫描文件列表

        Args:
            progress_callback: 进度回调

        Returns:
            文档列表
        """
        docs = []

        try:
            # 滚动加载所有项目
            self._scroll_to_load_all_files()

            # 统一的主内容区域选择器（与_scan_subfolders一致）
            main_content_selectors = [
                '.sc-gSQGeZ',           # 私有部署主内容区（滚动容器）
                '.sc-jgrIVw',           # app-main 主内容
                '.main__content',
                '[role="list"]',
            ]

            main_content = None
            for sel in main_content_selectors:
                try:
                    main_content = self.page.query_selector(sel)
                    if main_content:
                        log(f"找到主内容区域: {sel}")
                        break
                except:
                    continue

            if main_content:
                # 在主内容区域内查找文档链接
                doc_links = main_content.query_selector_all('a[href*="/docx/"]')
                folder_links = main_content.query_selector_all('a[href*="/folder/"]')

                log(f"找到 {len(doc_links)} 个文档链接, {len(folder_links)} 个文件夹链接")

                # 处理文档链接
                for link in doc_links:
                    try:
                        href = link.get_attribute('href')
                        if not href:
                            continue

                        # 获取名称
                        name = link.inner_text().strip()
                        if not name:
                            # 尝试从子元素获取
                            name_elem = link.query_selector('.spark-title, [class*="title"], [class*="name"]')
                            if name_elem:
                                name = name_elem.inner_text().strip()

                        if not name or self._should_exclude(name):
                            continue

                        # 提取文档ID
                        doc_id = ''
                        if '/docx/' in href:
                            doc_id = href.split('/docx/')[-1].split('?')[0]

                        # 构建完整URL
                        if href.startswith('/'):
                            href = f"{self.navigator.domain}{href}"

                        docs.append({
                            'type': 'doc',
                            'id': doc_id,
                            'name': name,
                            'url': href,
                        })
                        self.scanned_count += 1
                        log(f"  找到文档: {name[:30]}")

                        if progress_callback:
                            progress_callback(self.scanned_count, name)

                    except Exception as e:
                        log(f"  处理链接失败: {e}")
                        continue

            else:
                log("未找到主内容区域，尝试备用方法")

                # 方法2: 备用 - 直接查找所有文档链接
                all_links = self.page.query_selector_all('a[href*="/docx/"]')

                # 获取侧边栏以过滤
                sidebar = self.page.query_selector('.sc-cxpRKc, [class*="sidebar"]')
                sidebar_links = set()
                if sidebar:
                    sidebar_links = set(sidebar.query_selector_all('a'))

                for link in all_links:
                    if link in sidebar_links:
                        continue

                    try:
                        href = link.get_attribute('href')
                        if not href:
                            continue

                        name = link.inner_text().strip()
                        if not name or self._should_exclude(name):
                            continue

                        doc_id = ''
                        if '/docx/' in href:
                            doc_id = href.split('/docx/')[-1].split('?')[0]

                        if href.startswith('/'):
                            href = f"{self.navigator.domain}{href}"

                        docs.append({
                            'type': 'doc',
                            'id': doc_id,
                            'name': name,
                            'url': href,
                        })
                        self.scanned_count += 1
                        log(f"  找到文档: {name[:30]}")

                    except:
                        continue

        except Exception as e:
            log(f"扫描文件列表失败: {e}")

        return docs

    def _scan_subfolders(self) -> List[Dict]:
        """扫描子文件夹 - 只从主内容区域的文件列表中提取"""
        subfolders = []

        try:
            # 首先找到侧边栏元素，用于排除
            sidebar_selectors = [
                '.sc-cxpRKc',
                '[class*="sidebar"]',
                '.spark-tree',
                '[class*="nav-tree"]',
            ]
            sidebar = None
            for sel in sidebar_selectors:
                try:
                    sidebar = self.page.query_selector(sel)
                    if sidebar:
                        log(f"    找到侧边栏: {sel}")
                        break
                except:
                    continue

            # 找到面包屑导航区域，也用于排除
            breadcrumb_selectors = [
                '.breadcrumb',
                '[class*="breadcrumb"]',
                '.nav-path',
            ]
            breadcrumb_area = None
            for sel in breadcrumb_selectors:
                try:
                    breadcrumb_area = self.page.query_selector(sel)
                    if breadcrumb_area:
                        log(f"    找到面包屑区域: {sel}")
                        break
                except:
                    continue

            # 在主内容区域查找文件夹链接（与_scan_file_list使用相同选择器）
            main_content_selectors = [
                '.sc-gSQGeZ',           # 私有部署主内容区（滚动容器）
                '.sc-jgrIVw',           # app-main 主内容
                '.main__content',
                '[role="list"]',
            ]

            main_content = None
            for sel in main_content_selectors:
                try:
                    main_content = self.page.query_selector(sel)
                    if main_content:
                        # 确保不是侧边栏
                        if sidebar:
                            try:
                                # 检查main_content是否在sidebar内
                                is_in_sidebar = main_content.evaluate(
                                    f'el => el.closest(".sc-cxpRKc, [class*=sidebar], .spark-tree") !== null'
                                )
                                if is_in_sidebar:
                                    log(f"    跳过侧边栏内的元素: {sel}")
                                    continue
                            except:
                                pass
                        log(f"    找到主内容区域: {sel}")
                        break
                except:
                    continue

            if not main_content:
                log("    未找到主内容区域")
                return subfolders

            # 查找文件夹链接
            folder_links = main_content.query_selector_all('a[href*="/folder/"]')
            log(f"    在主内容区域找到 {len(folder_links)} 个文件夹链接")

            for link in folder_links:
                try:
                    href = link.get_attribute('href')
                    if not href:
                        log(f"    [DEBUG] 链接无href，跳过")
                        continue

                    # 提取链接的folder_id
                    link_folder_id = ''
                    if '/folder/' in href:
                        link_folder_id = href.split('/folder/')[-1].split('?')[0]

                    if not link_folder_id:
                        log(f"    [DEBUG] 链接无folder_id: {href[:50]}")
                        continue

                    # 排除当前文件夹自己的链接
                    current_folder_id = ''
                    current_url = self.page.url
                    if '/folder/' in current_url:
                        current_folder_id = current_url.split('/folder/')[-1].split('?')[0]

                    if link_folder_id == current_folder_id:
                        log(f"    [DEBUG] 链接指向当前文件夹，跳过")
                        continue

                    # 排除面包屑导航中的链接
                    if breadcrumb_area:
                        try:
                            is_in_breadcrumb = link.evaluate(
                                'el => el.closest(".breadcrumb, [class*=breadcrumb], .nav-path") !== null'
                            )
                            if is_in_breadcrumb:
                                log(f"    [DEBUG] 链接在面包屑中，跳过: {link_folder_id[:8]}")
                                continue
                        except:
                            pass

                    # 获取名称
                    name = link.inner_text().strip()
                    if not name:
                        name_elem = link.query_selector('.spark-title, [class*="title"], [class*="name"]')
                        if name_elem:
                            name = name_elem.inner_text().strip()

                    if not name or self._should_exclude(name):
                        log(f"    [DEBUG] 名称被排除: {name[:20] if name else '空'}")
                        continue

                    # 构建完整URL
                    if href.startswith('/'):
                        href = f"{self.navigator.domain}{href}"

                    subfolders.append({
                        'id': link_folder_id,
                        'name': name,
                        'url': href,
                    })
                    log(f"    ✓ 找到子文件夹: {name[:30]} ({link_folder_id[:8]})")

                except Exception as e:
                    log(f"    [DEBUG] 处理链接失败: {e}")
                    continue

        except Exception as e:
            log(f"  扫描子文件夹失败: {e}")

        return subfolders

    def _scroll_to_load_all_files(self):
        """滚动加载所有文件"""
        try:
            last_count = 0
            no_change_count = 0

            while no_change_count < 3:
                # 滚动到底部
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(SCROLL_WAIT_TIME)

                # 检查文件数量
                current_count = len(self.page.query_selector_all('[data-id], .file-list-item, .doc-list-item'))

                if current_count == last_count:
                    no_change_count += 1
                else:
                    no_change_count = 0
                    last_count = current_count

        except:
            pass

    def _extract_doc_info(self, item) -> Optional[Dict]:
        """从列表项提取文档信息"""
        try:
            # 先检查是否是文件夹
            if self._is_folder_item(item):
                return None

            name = self._get_item_name(item)
            if not name:
                return None

            # 获取URL
            url = None
            link = item.query_selector('a')
            if link:
                url = link.get_attribute('href')

            if not url:
                url = item.get_attribute('data-url') or item.get_attribute('data-href')

            # 获取文档ID
            doc_id = item.get_attribute('data-id') or item.get_attribute('data-doc-id')
            if not doc_id:
                doc_id = hashlib.md5(name.encode()).hexdigest()[:12]

            # 构造URL
            if not url:
                url = f"{self.navigator.domain}/docx/{doc_id}"

            return {
                'type': 'doc',
                'id': doc_id,
                'name': name,
                'url': url,
            }

        except:
            return None

    def _is_folder_item(self, item) -> bool:
        """判断是否是文件夹"""
        try:
            # 检查class属性（私有部署版本）
            class_name = item.get_attribute('class') or ''
            if 'folder' in class_name.lower():
                return True
            if 'docx' in class_name.lower() or 'doc' in class_name.lower():
                return False

            # 检查spark-item类型
            if 'spark-item' in class_name:
                # spark-item-container folder 或类似
                parent = item.evaluate('el => el.parentElement?.className || ""')
                if 'folder' in str(parent).lower():
                    return True

            # 检查整个item的HTML
            html = item.evaluate('el => el.outerHTML')
            if 'file-item-folder' in html:
                return True
            if 'file-item-docx' in html or 'file-item-doc' in html:
                return False

            # 检查链接URL（文件夹链接包含/folder/）
            link = item.query_selector('a')
            if link:
                href = link.get_attribute('href')
                if href and '/folder/' in href:
                    return True

            return False
        except:
            return False

    def _get_item_name(self, item) -> Optional[str]:
        """获取项目名称"""
        # 飞书私有部署版本的文档名称选择器
        name_selectors = [
            '.spark-title',           # 私有部署spark组件
            '[class*="spark-title"]',
            '[data-e2e="file-list-item"] .file-item-name',
            '.file-item-name',
            '.file-name',
            '.name',
            '.title',
            '[class*="name"]',
            '[title]',
        ]

        for selector in name_selectors:
            try:
                name_elem = item.query_selector(selector)
                if name_elem:
                    # 尝试获取title属性或文本内容
                    name = name_elem.get_attribute('title')
                    if not name:
                        name = name_elem.inner_text()
                    if name and len(name) > 0:
                        return name.strip()
            except:
                continue

        # 直接从item获取title属性
        try:
            name = item.get_attribute('title')
            if name:
                return name.strip()
        except:
            pass

        return None

    def _should_exclude(self, name: str) -> bool:
        """检查是否应该排除"""
        name_lower = name.lower()
        for pattern in SCAN_EXCLUDE_PATTERNS:
            if pattern.lower() in name_lower:
                return True
        return False

    def _try_api_intercept(self, folder_id: str) -> Optional[Dict]:
        """
        尝试通过拦截API响应获取文件列表

        飞书私有部署可能使用以下API获取文件夹内容：
        - /drive/api/v2/folders/{id}/children
        - /space/api/v1/files/list
        - 通过刷新页面触发API请求

        Args:
            folder_id: 文件夹ID

        Returns:
            包含docs和subfolders的字典，或None
        """
        import json as json_module

        captured_responses = []

        def on_response(response):
            url = response.url
            # 捕获可能的文件列表API
            if 'children' in url or 'list' in url or 'files' in url:
                if 'explorer' in url or 'space' in url or folder_id[:8] in url:
                    try:
                        if response.status == 200:
                            # 尝试直接解析JSON，不截取
                            try:
                                data = response.json()
                                log(f"    [API] 拦截到JSON响应: {url[:60]}...")
                                captured_responses.append({
                                    'url': url,
                                    'data': data
                                })
                            except:
                                # 如果JSON解析失败，记录URL
                                log(f"    [API] 拦截到响应(JSON解析失败): {url[:60]}...")
                    except Exception as e:
                        log(f"    [API] 读取响应失败: {e}")

        # 添加响应监听器
        self.page.on('response', on_response)

        try:
            # 刷新页面触发API请求
            log(f"    [API] 刷新页面触发API请求...")
            self.page.reload(wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # 处理捕获的响应
            if captured_responses:
                log(f"    [API] 拦获到 {len(captured_responses)} 个响应")
                for resp in captured_responses:
                    log(f"    [API] 响应URL: {resp['url'][:80]}")
                    # 直接使用解析好的JSON数据
                    if 'data' in resp:
                        data = resp['data']
                        log(f"    [API] 数据解析成功")
                        # 飞书私有部署API结构: data.data.entities 或 data.data.node_list
                if isinstance(data, dict):
                    log(f"    [API] 顶层键: {list(data.keys())[:10]}")
                    inner_data = data.get('data', {})
                    if isinstance(inner_data, dict):
                        log(f"    [API] data.data键: {list(inner_data.keys())[:10]}")
                        # 飞书私有部署的文件列表在 entities 或 node_list 中
                        entities = inner_data.get('entities', [])
                        node_list = inner_data.get('node_list', [])
                        log(f"    [API] entities数量: {len(entities)}, node_list数量: {len(node_list)}")

                        # 打印第一个entity的完整结构
                        if entities and len(entities) > 0:
                            first_entity = entities[0]
                            log(f"    [API] 第一个entity类型: {type(first_entity).__name__}")
                            if isinstance(first_entity, dict):
                                log(f"    [API] entity键: {list(first_entity.keys())}")
                                log(f"    [API] entity内容: {str(first_entity)[:300]}")

                        # 打印node_list第一个元素
                        if node_list and len(node_list) > 0:
                            first_node = node_list[0]
                            log(f"    [API] 第一个node类型: {type(first_node).__name__}, 值: {str(first_node)[:50]}")
                        # 查找文件列表
                        docs, subfolders = self._parse_api_file_list(data, folder_id)
                        if docs or subfolders:
                            log(f"    [API] 从API获取: {len(docs)} 个文档, {len(subfolders)} 个文件夹")
                            return {'docs': docs, 'subfolders': subfolders}

            log(f"    [API] 未找到有效的文件列表数据")
            return None

        except Exception as e:
            log(f"    [API] 拦截失败: {e}")
            return None

        finally:
            # 移除监听器
            try:
                self.page.remove_listener('response', on_response)
            except:
                pass

    def _parse_api_file_list(self, data: Dict, folder_id: str) -> Tuple[List, List]:
        """
        解析API响应中的文件列表

        飞书私有部署API结构示例：
        {
          "code": 0,
          "msg": "success",
          "data": {
            "entities": [...],  // 文件实体列表
            "node_list": [...], // 节点列表
            "has_more": false,
            "total": 10
          }
        }

        Args:
            data: API响应JSON
            folder_id: 当前文件夹ID

        Returns:
            (docs列表, subfolders列表)
        """
        docs = []
        subfolders = []

        try:
            # 飞书私有部署的响应结构
            if isinstance(data, dict):
                inner_data = data.get('data', {})
                if isinstance(inner_data, dict):
                    # 主要从 entities 或 node_list 获取
                    entities = inner_data.get('entities', [])
                    node_list = inner_data.get('node_list', [])

                    # 两个列表可能分别包含不同类型的内容
                    # entities: 完整的实体对象列表（dict）
                    # node_list: token列表（字符串）
                    log(f"    [API] entities数量: {len(entities)}, node_list数量: {len(node_list)}")

                    # 检查node_list的类型
                    if node_list and len(node_list) > 0:
                        first_node = node_list[0]
                        log(f"    [API] node_list第一个元素类型: {type(first_node).__name__}")
                        if isinstance(first_node, str):
                            log(f"    [API] node_list是token字符串列表，有 {len(node_list)} 个文档token")
                            # node_list是token列表，直接用token构造文档列表
                            # 同时使用entities获取文件夹信息
                            docs_from_tokens = []
                            for token in node_list:
                                docs_from_tokens.append({
                                    'token': token,
                                    'name': f'文档_{token[:8]}',
                                    'type': 'doc',
                                    'obj_type': 1  # 默认作为文档
                                })

                            # 处理entities（可能是文件夹或文档）
                            folders_from_entities = []
                            docs_from_entities = []
                            for entity in entities:
                                if isinstance(entity, dict):
                                    log(f"    [API] entity键: {list(entity.keys())[:10]}")
                                    log(f"    [API] entity: {str(entity)[:200]}")
                                    entity_type = entity.get('type') or entity.get('obj_type', '')
                                    entity_name = entity.get('name', f'文件夹_{entity.get("token", "")[:8]}')
                                    entity_token = entity.get('token', '')
                                    # 打印更多字段
                                    log(f"    [API] entity: token={entity_token[:8]}, type={entity_type}, name={entity_name[:20]}")
                                    # 检查是否有doc_token字段
                                    doc_token = entity.get('doc_token') or entity.get('url_token') or entity.get('obj_token', '')
                                    if doc_token:
                                        log(f"    [API] 发现doc_token: {doc_token[:20]}")
                                        docs_from_entities.append({
                                            'id': doc_token,
                                            'name': entity_name,
                                            'url': f"{self.navigator.domain}/docx/{doc_token}",
                                        })
                                    elif entity_type in ['folder', 2]:
                                        folders_from_entities.append({
                                            'id': entity_token,
                                            'name': entity_name,
                                            'url': f"{self.navigator.domain}/drive/folder/{entity_token}",
                                        })
                                    else:
                                        # 尝试将entity token作为doc token
                                        log(f"    [API] 尝试使用entity token作为doc token")
                                        docs_from_entities.append({
                                            'id': entity_token,
                                            'name': entity_name,
                                            'url': f"{self.navigator.domain}/docx/{entity_token}",
                                        })

                            log(f"    [API] 从token列表构造: {len(docs_from_tokens)} 个文档, {len(docs_from_entities)} 个实体文档, {len(folders_from_entities)} 个文件夹")

                            # 优先使用 entities 中的文档（可能包含正确的 doc token）
                            if docs_from_entities:
                                log(f"    [API] 使用entities中的文档")
                                docs = docs_from_entities
                            else:
                                docs = []
                                for doc in docs_from_tokens:
                                    docs.append({
                                        'type': 'doc',
                                        'id': doc['token'],
                                        'name': doc['name'],
                                        'url': f"{self.navigator.domain}/docx/{doc['token']}",
                                    })

                            if docs or folders_from_entities:
                                return docs, folders_from_entities  # 返回元组，不是字典
                        else:
                            # node_list是对象列表，使用它
                            items = node_list
                    else:
                        items = entities

                    log(f"    [API] 使用 {len(items)} 个项目进行解析")

                    # 打印第一个项目的结构用于调试
                    if items:
                        first_item = items[0]
                        log(f"    [API] 第一个项目类型: {type(first_item).__name__}")
                        if isinstance(first_item, dict):
                            log(f"    [API] 示例项目键: {list(first_item.keys())[:15]}")
                            log(f"    [API] token={first_item.get('token')}, id={first_item.get('id')}")

                    for item in items:
                        try:
                            if not isinstance(item, dict):
                                continue

                            # 获取ID (token/doc_id/id)
                            item_id = item.get('token') or item.get('doc_id') or item.get('id') or item.get('file_token', '')
                            if not item_id:
                                continue

                            # 获取名称
                            item_name = item.get('name') or item.get('title') or item.get('file_name', '未命名')

                            # 获取类型
                            item_type = item.get('type') or item.get('entity_type') or item.get('obj_type', '')
                            obj_sub_type = item.get('obj_sub_type', '')

                            log(f"    [API] 项目: {item_name[:20]} | 类型: {item_type}/{obj_sub_type} | ID: {item_id[:8]}")

                            # 判断是文档还是文件夹
                            # 文件夹类型
                            if item_type in ['folder', 'file_folder', 'bitable_folder'] or obj_sub_type in ['folder', 'bitable_folder']:
                                if item_id != folder_id:
                                    subfolders.append({
                                        'id': item_id,
                                        'name': item_name,
                                        'url': f"{self.navigator.domain}/drive/folder/{item_id}",
                                    })
                            # 文档类型
                            elif item_type in ['file', 'docx', 'doc', 'document', 'wiki'] or obj_sub_type in ['docx', 'doc', 'wiki']:
                                docs.append({
                                    'type': 'doc',
                                    'id': item_id,
                                    'name': item_name,
                                    'url': f"{self.navigator.domain}/docx/{item_id}",
                                })
                            else:
                                # 尝试从其他字段判断
                                file_extension = item.get('extension', '')

                                if file_extension in ['docx', 'doc']:
                                    docs.append({
                                        'type': 'doc',
                                        'id': item_id,
                                        'name': item_name,
                                        'url': f"{self.navigator.domain}/docx/{item_id}",
                                    })
                                # 默认作为文档处理
                                elif item.get('obj_type') == 1:  # obj_type=1通常是文档
                                    docs.append({
                                        'type': 'doc',
                                        'id': item_id,
                                        'name': item_name,
                                        'url': f"{self.navigator.domain}/docx/{item_id}",
                                    })

                        except Exception as e:
                            log(f"    [API] 解析项目失败: {e}")
                            continue

        except Exception as e:
            log(f"    [API] 解析文件列表失败: {e}")

        return docs, subfolders

    def debug_page_structure(self) -> str:
        """调试页面结构 - 输出HTML分析选择器"""
        from debug_helper import debug_page_structure as _debug
        return _debug(self.page)


if __name__ == '__main__':
    print("目录扫描模块 - 请通过 xianfeng_search.py 调用")