#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
站点配置模块

定义各网站的链接发现规则。
"""

# 网站别名
SITE_ALIASES = {
    'mpaypass': 'https://www.mpaypass.com.cn/',
    '移动支付网': 'https://www.mpaypass.com.cn/',
}

# 站点特定配置
SITE_CONFIGS = {
    'mpaypass.com.cn': {
        'name': '移动支付网',
        'link_patterns': [
            r'/news/\d{6}/\d{6,8}\.html',
        ],
        'exclude_patterns': [
            r'/tag/',
            r'/author/',
            r'/page/',
            r'\#',
            r'javascript:',
        ],
        'content_selector': '.article-content',
        'title_selector': 'h1',
    },
    'pbc.gov.cn': {
        'name': '中国人民银行',
        # 仅匹配 沟通交流>新闻 栏目（113469）下的文章详情页，如
        # /goutongjiaoliu/113456/113469/2026081015473613597/index.html
        'link_patterns': [
            r'/goutongjiaoliu/113456/113469/\d+/index\.html',
        ],
        'exclude_patterns': [],
        'content_selector': '',
        'title_selector': 'h1',
    },
    'shanghai.gov.cn': {
        'name': '上海市人民政府',
        # SPA 站点：列表由 JSON API 渲染，HTML 里无文章链接。
        # 用 api_list.py 通过 api 配置翻页拉取记录，构造详情 URL 后交给 fetcher.py 抓取。
        'link_patterns': [],
        'exclude_patterns': [],
        'api': {
            'url': 'https://www.shanghai.gov.cn/gwk/policy/page',
            'method': 'POST',
            'body_template': '{"siteIdList":["0001"],"pageNo":{page},"pageSize":{size}}',
            # record 顶层字段与 attrs 子字段均可用于模板占位符
            'url_template': 'https://www.shanghai.gov.cn/zhengce/detail?businessId={businessId}&siteId={siteId}',
        },
    },
    'sh.mof.gov.cn': {
        'name': '财政部上海监管局',
        # 工作动态栏目文章，如 /gzdt/caizhengjiancha/202608/t20260825_3996042.htm
        'link_patterns': [
            r'/gzdt/caizhengjiancha/\d{6}/t\d{8}_\d+\.htm',
        ],
        'exclude_patterns': [],
        'content_selector': '.TRS_Editor',
        'title_selector': 'h1',
    },
    # 可扩展其他站点配置
}

def get_site_config(url):
    """获取站点配置

    Args:
        url: 页面URL

    Returns:
        dict: 站点配置，如果未找到返回 None
    """
    for domain, config in SITE_CONFIGS.items():
        if domain in url:
            return config
    return None


def get_site_name(url):
    """从URL提取站点名称

    Args:
        url: 页面URL

    Returns:
        str: 站点名称
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')

    # 检查配置
    config = get_site_config(url)
    if config:
        return config.get('name')

    # 默认使用域名
    return domain.split('.')[0] if domain else 'unknown'