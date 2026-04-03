#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页内容解析模块

提供网页内容提取、清洗、反爬检测等功能。
纯函数，无副作用，方便测试和扩展。
"""

import re

# 尝试导入BS4
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# 广告关键词
AD_KEYWORDS = [
    '广告', '推广', '赞助', 'sponsored', 'advertisement',
    '点击下载', '立即下载', '免费下载', '扫码下载',
    '关注公众号', '扫码关注', '领取红包', '优惠券',
    '限时优惠', '秒杀', '拼团', '砍价',
]

# 广告域名
AD_DOMAINS = [
    'ad.', 'ads.', 'adv.', 'promotion.',
    'click.', 'track.', 'analytics.',
]


def extract_content(html, url='', max_length=15000):
    """从HTML中提取正文内容"""
    if HAS_BS4:
        soup = BeautifulSoup(html, 'html.parser')

        # 移除无用标签
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside',
                         'iframe', 'noscript', 'form', 'button', 'input']):
            tag.decompose()

        # 移除广告元素
        _remove_ads(soup)

        # 提取标题
        title = ''
        if soup.find('title'):
            title = soup.find('title').get_text(strip=True)
        elif soup.find('h1'):
            title = soup.find('h1').get_text(strip=True)

        # 提取正文
        content_text = _extract_main_content(soup)

    else:
        # 无BS4时的简单提取
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ''

        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        content_text = text

    # 智能清理内容
    content_text = smart_clean_text(content_text)

    # 过滤广告段落
    content_text = filter_ad_paragraphs(content_text)

    # 截断
    if len(content_text) > max_length:
        content_text = content_text[:max_length] + '\n... (内容已截断)'

    return {
        'title': title,
        'content': content_text,
        'length': len(content_text)
    }


def _remove_ads(soup):
    """移除广告元素"""
    # 收集要删除的元素，避免在迭代中修改
    to_decompose = []

    for tag in soup.find_all(True):
        classes = ' '.join(tag.get('class', []))
        tag_id = tag.get('id', '')
        combined = f"{classes} {tag_id}".lower()

        if any(ad in combined for ad in ['ad-', 'ads-', 'adv-', 'banner', 'popup', 'modal']):
            to_decompose.append(tag)
            continue

        text = tag.get_text(strip=True)
        if len(text) < 100:
            if any(kw in text for kw in ['广告', '推广', '点击下载', '扫码']):
                to_decompose.append(tag)

    # 统一删除
    for tag in to_decompose:
        try:
            tag.decompose()
        except:
            pass


def _extract_main_content(soup):
    """从BeautifulSoup对象中提取主要内容"""
    content_selectors = [
        'article', 'main', '.content', '.article', '.post',
        '.entry-content', '.post-content', '#content',
        '.article-content', '.detail', '.body', '.text',
        '.main-content', '.lemma-summary', '.para',
    ]

    for selector in content_selectors:
        elements = soup.select(selector)
        if elements:
            best_elem = max(elements, key=lambda e: len(e.get_text()))
            return _extract_text_with_paragraphs(best_elem)

    if soup.find('body'):
        return _extract_text_with_paragraphs(soup.find('body'))

    return ''


def _extract_text_with_paragraphs(element):
    """从元素中提取文本"""
    text = element.get_text(separator=' ', strip=True)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def smart_clean_text(text):
    """智能清理文本：根据标点智能分段"""
    if not text:
        return ''

    # 清理多余空白
    text = re.sub(r'\s+', ' ', text).strip()

    # 根据句号分段
    text = re.sub(r'([。！？])\s*', r'\1\n', text)
    text = re.sub(r'([.!?])\s+([A-Z\u4e00-\u9fff])', r'\1\n\2', text)

    # 清理多余换行
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def filter_ad_paragraphs(text):
    """过滤广告段落"""
    lines = text.split('\n')
    filtered_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            filtered_lines.append('')
            continue

        is_ad = False
        line_lower = line.lower()

        for kw in AD_KEYWORDS:
            if kw in line_lower and len(line) < 50:
                is_ad = True
                break

        for domain in AD_DOMAINS:
            if domain in line_lower and 'http' in line_lower:
                is_ad = True
                break

        if not is_ad:
            filtered_lines.append(line)

    return '\n'.join(filtered_lines)


def check_anti_crawl(html, url=''):
    """检测是否遇到反爬/验证码"""
    html_lower = html.lower()
    url_lower = url.lower()

    anti_patterns = [
        '百度安全验证', 'wappass.baidu.com',
        '安全验证', '验证码', 'captcha',
        '请输入验证码', '访问过于频繁',
        '人机验证', '滑块验证',
        'security check', 'cloudflare', '验证您的身份',
        '访问被拒绝', 'access denied',
    ]

    for pattern in anti_patterns:
        if pattern in html_lower or pattern in url_lower:
            return True

    return False


def is_redirect_url(url):
    """检测是否是跳转链接"""
    redirect_patterns = [
        'baidu.com/link', 'baidu.com/baidu.php',
        'google.com/url', 'redirect', 'jump',
    ]
    return any(p in url for p in redirect_patterns)


def extract_links(html, base_url='', pattern=None):
    """从HTML中提取所有链接"""
    links = []

    if not HAS_BS4:
        link_pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', re.IGNORECASE)
        for match in link_pattern.finditer(html):
            url, text = match.groups()
            if pattern and not re.search(pattern, url):
                continue
            links.append({'url': url, 'text': text.strip()})
        return links

    soup = BeautifulSoup(html, 'html.parser')

    for a in soup.find_all('a', href=True):
        url = a.get('href', '')
        text = a.get_text(strip=True)

        if pattern and not re.search(pattern, url):
            continue

        if base_url and url.startswith('/'):
            from urllib.parse import urljoin
            url = urljoin(base_url, url)

        links.append({'url': url, 'text': text})

    return links


def extract_images(html, base_url=''):
    """从HTML中提取所有图片"""
    images = []

    if not HAS_BS4:
        img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*(?:alt=["\']([^"\']*)["\'])?[^>]*>', re.IGNORECASE)
        for match in img_pattern.finditer(html):
            url = match.group(1)
            alt = match.group(2) or ''
            images.append({'url': url, 'alt': alt})
        return images

    soup = BeautifulSoup(html, 'html.parser')

    for img in soup.find_all('img', src=True):
        url = img.get('src', '')
        alt = img.get('alt', '')

        if base_url and url.startswith('/'):
            from urllib.parse import urljoin
            url = urljoin(base_url, url)

        images.append({'url': url, 'alt': alt})

    return images


def clean_text(text):
    """清理文本"""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()