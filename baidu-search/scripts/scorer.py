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

# 索引/导航页特征(文档字母索引、目录页) -> 正文通常只有字母/标题跳转,无实质内容
INDEX_NAV_TITLE_PATTERNS = [
    r'^(索引|index|index\s*[-—–])',
    r'genindex',
    r'\b(the\s+index|full\s+index|module\s+index)\b',
]

# ============ 基于真实域名(real_domain)的权威评分 ============

# 跳过(极低分)的域名 - 视频/无正文站
DOMAIN_SKIP = [
    'bilibili.com', 'youtube.com', 'youtu.be', 'youku.com', 'iqiyi.com',
    'douyin.com', 'kuaishou.com', 'acfun.cn', 'ted.com', 'v.qq.com',
    'podcasts.apple.com', 'music.163.com',
]

# 精准域名 -> 基础分 (按权威度)
DOMAIN_PATTERN_SCORES = {
    # 官方文档 / 代码托管 / 权威参考
    'stackoverflow.com': 9.5,
    'github.com': 9.2,
    'python.org': 9.2,
    'developer.mozilla.org': 9.2,
    'nodejs.org': 9.0,
    'pypi.org': 9.0,
    'readthedocs.io': 9.0,
    'developer.chrome.com': 9.0,
    'react.dev': 9.0,
    'gitee.com': 8.8,
    # 高质量技术社区
    'juejin.cn': 8.0,
    'segmentfault.com': 8.0,
    'csdn.net': 7.5,
    'blog.csdn.net': 7.5,
    'zhihu.com': 7.0,
    'runoob.com': 6.5,
    'cnblogs.com': 6.0,
}

# 域名后缀 -> 基础分 (官方/权威机构)
DOMAIN_SUFFIX_SCORES = {
    '.gov.cn': 9.5,  # 政府机构
    '.gov': 9.0,
    '.edu.cn': 9.3,  # 高校教育机构
    '.edu': 9.0,
    '.ac.cn': 8.8,   # 科研机构
}


def _extract_domain(url: str) -> str:
    """从 URL 稳健提取主域名(小写)"""
    if not url:
        return ''
    u = url
    if '://' in u:
        u = u.split('://', 1)[1]
    u = u.split('/')[0]
    u = u.split(':')[0]
    u = u.split('@')[-1]
    return u.lower()


def _match_domain(real_domain: str, target: str) -> bool:
    """判断 real_domain 是否等于 target 或以其为子域"""
    return real_domain == target or real_domain.endswith('.' + target)


def _is_index_nav_page(title: str) -> bool:
    """判断标题是否为索引/导航页(如 docs 的字母索引),其正文通常无实质内容"""
    if not title:
        return False
    t = title.strip()
    # 中文/日文索引页: "索引 — Python 3.x 文档"、"색인 — ..."
    if re.match(r'^(索引|색인|目錄|目录)[\s\-—–:：]', t):
        return True
    # 英文索引页: "Index – N"、"The Python Index"
    if re.match(r'^(index|the\s+index)[\s\-—–:：]', t, re.IGNORECASE):
        return True
    # 含 genindex / full index / module index
    if re.search(r'\b(genindex|full\s+index|module\s+index)\b', t, re.IGNORECASE):
        return True
    return False

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
            result: 搜索结果字典，包含 title, url, abstract, real_url, real_domain
            query: 搜索关键词

        Returns:
            float: 质量分数 (0-10)
        """
        url = result.get('url', '') or ''
        real_url = result.get('real_url', '') or url
        # 优先使用调用方已还原的 real_domain；否则从 URL 兜底提取
        real_domain = (result.get('real_domain') or '').lower() or _extract_domain(real_url)

        title = result.get('title', '')
        abstract = result.get('abstract', '')
        text = f"{title} {abstract}".lower()

        # 1. 检查过滤项（含真实域名是否命中视频/无正文站）
        filtered_score = self._check_filters(text, url, real_url, real_domain)
        if filtered_score is not None:
            return filtered_score

        # 1.5 索引/导航页(如文档字母索引) -> 正文通常无实质内容,压低分
        if _is_index_nav_page(title):
            return 2.5

        # 2. 计算基础分 (真实域名优先，文本兜底)
        score = self._calculate_base_score(text, real_domain)

        # 3. 关键词匹配度加分
        if query:
            score += self._calculate_relevance_bonus(title, abstract, query)

        # 4. 内容类型加分
        score += self._calculate_content_bonus(text)

        # 5. 中文优先加分
        if query:
            score += self._calculate_language_bonus(title, query)

        return min(score, 10.0)

    def _check_filters(self, text: str, url: str, real_url: str = '', real_domain: str = '') -> float | None:
        """检查是否命中过滤项，返回过滤分数或 None"""
        # 真实域名命中视频/无正文站 -> 极低分(相当于跳过)
        if real_domain and any(_match_domain(real_domain, d) for d in DOMAIN_SKIP):
            return 0.5

        # 广告下载类
        if any(p in (url or real_url) or p in text for p in APP_PATTERNS):
            return 0.5

        # 营销推广类 (但教程类除外)
        if any(p in text for p in PROMO_PATTERNS) and '教程' not in text:
            return 1.0

        return None

    def _calculate_base_score(self, text: str, real_domain: str = '') -> float:
        """根据来源计算基础分（真实域名优先，文本兜底）"""
        # 1) 真实域名命中 - 精准权威判定
        if real_domain:
            base = self._domain_quality(real_domain)
            if base is not None:
                return base

        # 2) 官方文档 (文本兜底)
        if any(m in text for m in OFFICIAL_MARKERS):
            return 9.0

        # 3) 技术社区 (按优先级匹配 - 文本兜底)
        for pattern, score in TECH_SOURCE_SCORES.items():
            if re.search(pattern, text, re.IGNORECASE):
                return score

        # 4) 官方机构 (文本兜底)
        if any(m in text for m in ['.gov.cn', '.edu.cn', '官方']):
            return 8.5

        # 5) 视频平台
        if any(p in text for p in VIDEO_PLATFORMS):
            if any(k in text for k in VIDEO_TUTORIAL_KEYWORDS):
                return 6.5
            return 4.0

        # 6) 低质量内容
        if any(m in text for m in LOW_QUALITY_MARKERS):
            return 3.5

        return self.base_score

    def _domain_quality(self, real_domain: str) -> float | None:
        """根据真实域名返回权威等级分；无匹配返回 None"""
        if not real_domain:
            return None

        # 精准域名匹配（较高分优先）
        for domain, score in sorted(DOMAIN_PATTERN_SCORES.items(), key=lambda x: x[1], reverse=True):
            if _match_domain(real_domain, domain):
                return score

        # 官方/机构后缀匹配
        for suffix, score in sorted(DOMAIN_SUFFIX_SCORES.items(), key=lambda x: x[1], reverse=True):
            if real_domain.endswith(suffix):
                return score

        return None

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