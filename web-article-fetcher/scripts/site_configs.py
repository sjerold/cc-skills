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