#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索结果质量评分器

基于正则匹配的评分矩阵，评估搜索结果质量。
"""

import re
from typing import Dict, List, Any


# ============ 评分配置常量 ============

# 过滤项 - 广告下载类
APP_PATTERNS = [
    'app下载', '应用下载', '软件下载', '安卓版', '安装包',
    'sj.qq.com', 'appdetail', '32r.com', 'duote.com',
    '多多软件', '华军软件', '应用宝', 'play.google.com'
]

# 过滤项 - 营销推广类
PROMO_PATTERNS = ['官方旗舰店', '优惠券', '折扣', '促销', '秒杀']

# 官方文档标识
OFFICIAL_MARKERS = [
    'python.org', 'pypi.org', 'github.com', 'gitee.com',
    'readthedocs', '官方文档', 'documentation',
    '說明文件', '参考手册', '开发文档'
]

# 技术社区评分 (来源 -> 基础分)
TECH_SOURCE_SCORES = {
    # 高质量国际社区
    r'stack\s*overflow': 9.5,
    r'real\s*python': 9.0,
    'infoq': 8.5,
    # 国内优质社区
    '掘金': 8.0,
    'juejin': 8.0,
    'segmentfault': 8.0,
    '思否': 8.0,
    'csdn': 7.5,
    '知乎': 7.0,
    'zhihu': 7.0,
    # 教程网站
    '菜鸟教程': 6.5,
    'runoob': 6.5,
    '博客园': 6.0,
    'cnblogs': 6.0,
    '脚本之家': 5.5,
    'jb51': 5.5,
}

# 视频平台
VIDEO_PLATFORMS = ['bilibili', '哔哩哔哩', 'youtube', '优酷']

# 视频教程关键词
VIDEO_TUTORIAL_KEYWORDS = ['教程', 'tutorial', '讲解', '入门', '完整']

# 低质量内容标识
LOW_QUALITY_MARKERS = ['百度文库', '百度知道', '贴吧', '文库精选']

# 高价值内容类型
HIGH_VALUE_PATTERNS = [
    '教程', 'tutorial', '指南', 'guide', '详解', '入门',
    '完整', '实战', '案例', '示例', '最佳实践', '全攻略'
]

# 问题解答类关键词
QA_PATTERNS = ['如何', '怎么', '解决', '问题', '错误', '报错', 'bug', '方法']


class SearchResultScorer:
    """搜索结果评分器"""

    def __init__(self, base_score: float = 5.0):
        self.base_score = base_score

    def score(self, result: Dict[str, Any], query: str = '') -> float:
        """
        计算搜索结果质量分数

        Args:
            result: 搜索结果字典，包含 title, url, abstract
            query: 搜索关键词

        Returns:
            float: 质量分数 (0-10)
        """
        url = result.get('url', '').lower()
        title = result.get('title', '')
        abstract = result.get('abstract', '')
        text = f"{title} {abstract}".lower()

        # 1. 检查过滤项
        filtered_score = self._check_filters(text, url)
        if filtered_score is not None:
            return filtered_score

        # 2. 计算基础分 (根据来源)
        score = self._calculate_base_score(text)

        # 3. 关键词匹配度加分
        if query:
            score += self._calculate_relevance_bonus(title, abstract, query)

        # 4. 内容类型加分
        score += self._calculate_content_bonus(text)

        # 5. 中文优先加分
        if query:
            score += self._calculate_language_bonus(title, query)

        return min(score, 10.0)

    def _check_filters(self, text: str, url: str) -> float | None:
        """检查是否命中过滤项，返回过滤分数或 None"""
        # 广告下载类
        if any(p in url or p in text for p in APP_PATTERNS):
            return 0.5

        # 营销推广类 (但教程类除外)
        if any(p in text for p in PROMO_PATTERNS) and '教程' not in text:
            return 1.0

        return None

    def _calculate_base_score(self, text: str) -> float:
        """根据来源计算基础分"""
        # 官方文档
        if any(m in text for m in OFFICIAL_MARKERS):
            return 9.0

        # 技术社区 (按优先级匹配)
        for pattern, score in TECH_SOURCE_SCORES.items():
            if re.search(pattern, text, re.IGNORECASE):
                return score

        # 官方机构
        if any(m in text for m in ['.gov.cn', '.edu.cn', '官方']):
            return 8.5

        # 视频平台
        if any(p in text for p in VIDEO_PLATFORMS):
            if any(k in text for k in VIDEO_TUTORIAL_KEYWORDS):
                return 6.5
            return 4.0

        # 低质量内容
        if any(m in text for m in LOW_QUALITY_MARKERS):
            return 3.5

        return self.base_score

    def _calculate_relevance_bonus(self, title: str, abstract: str, query: str) -> float:
        """计算关键词匹配度加分"""
        query_words = [w for w in query.lower().split() if len(w) > 1]
        if not query_words:
            return 0.0

        bonus = 0.0
        title_lower = title.lower()

        # 标题匹配度
        title_matches = sum(1 for w in query_words if w in title_lower)
        match_ratio = title_matches / len(query_words)

        if match_ratio >= 0.8:
            bonus += 1.5  # 标题高度匹配
        elif match_ratio >= 0.5:
            bonus += 0.8  # 标题部分匹配

        # 摘要匹配度
        abstract_lower = abstract.lower()
        abstract_matches = sum(1 for w in query_words if w in abstract_lower)
        if abstract_matches >= len(query_words) * 0.5:
            bonus += 0.5

        return bonus

    def _calculate_content_bonus(self, text: str) -> float:
        """计算内容类型加分"""
        bonus = 0.0

        # 高价值内容类型
        if any(p in text for p in HIGH_VALUE_PATTERNS):
            bonus += 0.8

        # 问题解答类
        if any(p in text for p in QA_PATTERNS):
            bonus += 0.3

        return bonus

    def _calculate_language_bonus(self, title: str, query: str) -> float:
        """计算语言匹配加分"""
        # 中文搜索优先中文标题
        if any(ord(c) > 127 for c in query):
            if any(ord(c) > 127 for c in title):
                return 0.3
        return 0.0


def calculate_quality_score(result: Dict[str, Any], query: str = '') -> float:
    """
    计算搜索结果质量分数 (便捷函数)

    Args:
        result: 搜索结果字典
        query: 搜索关键词

    Returns:
        float: 质量分数 (0-10)
    """
    scorer = SearchResultScorer()
    return scorer.score(result, query)


def score_results(results: List[Dict[str, Any]], query: str = '') -> List[Dict[str, Any]]:
    """
    为搜索结果列表评分 (原地修改)

    Args:
        results: 搜索结果列表
        query: 搜索关键词

    Returns:
        List: 带评分的结果列表
    """
    scorer = SearchResultScorer()
    for result in results:
        result['score'] = scorer.score(result, query)
    return results