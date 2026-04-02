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
from typing import Dict, List, Optional, Callable

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
        print("开始扫描当前文件夹...", file=sys.stderr)

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

            print(f"当前URL: {current_url}", file=sys.stderr)

            # 如果URL不包含预期的folder_id，尝试等待
            if expected_folder_id and expected_folder_id not in current_url:
                print(f"等待页面导航到正确位置...", file=sys.stderr)
                for i in range(10):
                    time.sleep(1)
                    current_url = self.page.url
                    if expected_folder_id in current_url:
                        print(f"页面已稳定: {current_url}", file=sys.stderr)
                        break
                    print(f"  等待中... ({i+1}/10) URL: {current_url[:50]}...", file=sys.stderr)

            # 尝试触发虚拟列表渲染
            self._trigger_list_render()

            # 额外等待渲染完成
            time.sleep(3)

            # 再次检查当前URL
            current_url = self.page.url
            print(f"扫描前URL: {current_url}", file=sys.stderr)

            # 获取当前文件夹名称
            folder_name = self._get_current_folder_name()

            # 从父目录缓存中获取完整路径（优先使用）
            folder_info = find_folder_info_from_parent_cache(folder_id)
            if folder_info.get('folder_path'):
                folder_path = folder_info['folder_path']
            else:
                folder_path = folder_name

            print(f"文件夹: {folder_name} (ID: {folder_id})", file=sys.stderr)
            print(f"完整路径: {folder_path}", file=sys.stderr)

            # 获取文件夹最后修改时间
            last_modified = self._get_folder_last_modified()
            if last_modified:
                print(f"最后修改时间: {last_modified}", file=sys.stderr)

            # 尝试从文件列表扫描
            docs = self._scan_file_list(progress_callback)

            # 尝试获取子文件夹
            subfolders = self._scan_subfolders()
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

            print(f"\n扫描完成: {len(docs)} 个文档, {len(subfolders)} 个子文件夹", file=sys.stderr)

            return cache_entry

        except Exception as e:
            print(f"扫描失败: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return None

    def _trigger_list_render(self):
        """尝试触发虚拟列表渲染"""
        try:
            # 等待网络空闲
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass

            # 方法1: 点击右侧文件区域
            right_panel_selectors = [
                '.sc-gSQGeZ',
                '.main__content',
                '[class*="explorer"]',
            ]

            for selector in right_panel_selectors:
                try:
                    elem = self.page.query_selector(selector)
                    if elem:
                        elem.click(timeout=2000)
                        time.sleep(1)
                        print(f"点击右侧区域: {selector}", file=sys.stderr)
                        break
                except:
                    continue

            # 方法2: 滚动右侧面板
            self.page.evaluate('''
                () => {
                    const panel = document.querySelector('.sc-gSQGeZ') ||
                                  document.querySelector('.main__content');
                    if (panel) {
                        panel.scrollTop = 100;
                        setTimeout(() => { panel.scrollTop = 0; }, 500);
                    }
                }
            ''')
            time.sleep(1)

            # 方法3: 按键触发
            self.page.keyboard.press('Tab')
            time.sleep(0.5)
            self.page.keyboard.press('ArrowDown')
            time.sleep(0.5)
            self.page.keyboard.press('ArrowUp')

            # 方法4: 等待虚拟列表渲染
            for _ in range(10):
                items = self.page.query_selector_all('[role="item"]')
                if len(items) > 0:
                    print(f"虚拟列表已渲染: {len(items)} 个项目", file=sys.stderr)
                    break
                time.sleep(0.5)

        except Exception as e:
            print(f"触发渲染失败: {e}", file=sys.stderr)

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
        # 优先从面包屑导航获取（最后一个元素是当前文件夹）
        breadcrumb_selectors = [
            '.breadcrumb-item:last-child',
            '.nav-path-item:last-child',
            '[class*="breadcrumb"] span:last-child',
            '.folder-path:last-child',
        ]

        for selector in breadcrumb_selectors:
            try:
                elem = self.page.query_selector(selector)
                if elem:
                    name = elem.inner_text().strip()
                    if name and len(name) < 100 and name != 'Home':
                        return name
            except:
                continue

        # 从页面标题获取（排除"Home"）
        name_selectors = [
            '.drive-header-title',
            '.folder-title',
            '.current-folder-name',
            'h1',
            '[class*="title"]',
        ]

        for selector in name_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                for elem in elements:
                    name = elem.inner_text().strip()
                    if name and len(name) < 100 and name != 'Home':
                        return name
            except:
                continue

        # 从URL提取文件夹ID作为备选
        url = self.page.url
        if '/folder/' in url:
            return f"文件夹_{url.split('/folder/')[-1].split('?')[0][:8]}"

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

            # 飞书文件列表项选择器（根据调试结果更新）
            item_selectors = [
                '[role="item"]',           # 飞书主要选择器
                '.file-list-item',         # 飞书备用选择器
                '[data-e2e="file-list-item"]',  # 飞书数据属性
            ]

            items = []
            for selector in item_selectors:
                try:
                    items = self.page.query_selector_all(selector)
                    if items:
                        print(f"找到 {len(items)} 个列表项 ({selector})", file=sys.stderr)
                        break
                except Exception as e:
                    print(f"选择器 {selector} 错误: {e}", file=sys.stderr)
                    continue

            if not items:
                print("未找到任何列表项！", file=sys.stderr)
                # 尝试其他选择器
                items = self.page.query_selector_all('[data-id]')

            for i, item in enumerate(items):
                try:
                    doc_info = self._extract_doc_info(item)
                    if doc_info and doc_info.get('name'):
                        docs.append(doc_info)
                        self.scanned_count += 1
                        print(f"  找到文档: {doc_info.get('name', 'N/A')[:30]}", file=sys.stderr)

                        if progress_callback:
                            progress_callback(self.scanned_count, doc_info['name'])
                    else:
                        # 调试：输出为什么没有提取到文档
                        if i < 5:  # 只输出前5个
                            try:
                                html = item.evaluate('el => el.outerHTML[:200]')
                                print(f"  项目 {i} 未提取到名称，HTML: {html}", file=sys.stderr)
                            except:
                                pass

                except Exception as e:
                    print(f"  提取项目 {i} 失败: {e}", file=sys.stderr)
                    continue

        except Exception as e:
            print(f"扫描文件列表失败: {e}", file=sys.stderr)

        return docs

    def _scan_subfolders(self) -> List[Dict]:
        """扫描子文件夹 - 从文件列表项中提取"""
        subfolders = []

        try:
            # 从文件列表项中提取子文件夹（而非侧边栏）
            items = self.page.query_selector_all('[role="item"]')

            for item in items:
                try:
                    # 检查是否是文件夹 (data-type="0" 或 class包含 file-item-folder)
                    html = item.evaluate('el => el.outerHTML')
                    is_folder = 'file-item-folder' in html or 'data-type="0"' in html

                    if not is_folder:
                        continue

                    # 获取文件夹名称
                    name = self._get_item_name(item)
                    if not name or self._should_exclude(name):
                        continue

                    # 获取文件夹链接（正确的ID）
                    link = item.query_selector('a')
                    if link:
                        href = link.get_attribute('href')
                        if href and '/folder/' in href:
                            # 从链接提取ID: /drive/folder/XXX
                            folder_id = href.split('/folder/')[-1].split('?')[0]
                            subfolders.append({
                                'id': folder_id,
                                'name': name,
                                'url': href,
                            })
                            print(f"  找到子文件夹: {name} ({folder_id})", file=sys.stderr)

                except Exception as e:
                    continue

        except Exception as e:
            print(f"扫描子文件夹失败: {e}", file=sys.stderr)

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
            # 检查整个item的HTML
            html = item.evaluate('el => el.outerHTML')
            if 'file-item-folder' in html:
                return True
            if 'file-item-docx' in html or 'file-item-doc' in html:
                return False

            # 检查class属性
            class_name = item.get_attribute('class') or ''
            if 'folder' in class_name.lower() and 'file-item-folder' not in html:
                return True

            return False
        except:
            return False

    def _get_item_name(self, item) -> Optional[str]:
        """获取项目名称"""
        # 飞书私有部署版本的文档名称选择器
        name_selectors = [
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

        return None

    def _should_exclude(self, name: str) -> bool:
        """检查是否应该排除"""
        name_lower = name.lower()
        for pattern in SCAN_EXCLUDE_PATTERNS:
            if pattern.lower() in name_lower:
                return True
        return False

    def debug_page_structure(self) -> str:
        """调试页面结构 - 输出HTML分析选择器"""
        from debug_helper import debug_page_structure as _debug
        return _debug(self.page)


if __name__ == '__main__':
    print("目录扫描模块 - 请通过 xianfeng_search.py 调用")