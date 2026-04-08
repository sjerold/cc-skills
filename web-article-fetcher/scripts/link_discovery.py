#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
链接发现模块 - Clean Code 版本

单一职责：从网页中发现文章链接
"""

import re
from urllib.parse import urljoin
from typing import List, Dict, Optional

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


class LinkFinder:
    """链接发现器"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def find(self, base_url: str, html: str) -> List[Dict[str, str]]:
        """发现页面中的文章链接"""
        if HAS_BS4:
            return self._find_with_bs4(base_url, html)
        return self._find_with_regex(base_url, html)

    def _find_with_bs4(self, base_url: str, html: str) -> List[Dict[str, str]]:
        """使用 BeautifulSoup 解析"""
        soup = BeautifulSoup(html, 'html.parser')
        candidates = []

        for anchor in soup.find_all('a', href=True):
            url = self._normalize_url(base_url, anchor['href'])
            if self._is_valid_article_url(url):
                candidates.append({'url': url})

        return self._deduplicate(candidates)

    def _find_with_regex(self, base_url: str, html: str) -> List[Dict[str, str]]:
        """使用正则解析（备选方案）"""
        patterns = self._get_link_patterns()
        candidates = []

        for pattern in patterns:
            for match in re.finditer(pattern, html):
                href = match.group(0)
                url = urljoin(base_url, href)
                candidates.append({'url': url})

        return self._deduplicate(candidates)

    def _normalize_url(self, base_url: str, href: str) -> str:
        """标准化URL"""
        return urljoin(base_url, href)

    def _is_valid_article_url(self, url: str) -> bool:
        """验证是否为有效文章URL"""
        if not url.startswith(('http://', 'https://')):
            return False

        if self._matches_exclude_patterns(url):
            return False

        if not self._matches_link_patterns(url):
            return False

        return True

    def _matches_exclude_patterns(self, url: str) -> bool:
        """检查是否匹配排除模式"""
        exclude_patterns = self.config.get('exclude_patterns', [])
        for pattern in exclude_patterns:
            if re.search(pattern, url):
                return True
        return False

    def _matches_link_patterns(self, url: str) -> bool:
        """检查是否匹配链接模式"""
        link_patterns = self.config.get('link_patterns', [])
        if not link_patterns:
            return True  # 无模式时全部通过

        for pattern in link_patterns:
            if re.search(pattern, url):
                return True
        return False

    def _get_link_patterns(self) -> List[str]:
        """获取链接模式"""
        return self.config.get('link_patterns', [r'/news/\d+/\d+\.html'])

    def _deduplicate(self, items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """去重"""
        seen = set()
        unique = []
        for item in items:
            if item['url'] not in seen:
                seen.add(item['url'])
                unique.append(item)
        return unique


# 便捷函数
def discover_links(base_url: str, html: str, config: Optional[Dict] = None) -> List[Dict[str, str]]:
    """发现文章链接"""
    finder = LinkFinder(config)
    return finder.find(base_url, html)