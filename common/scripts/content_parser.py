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
                         'iframe', 'noscript', 'form', 'button', 'input', 'svg']):
            tag.decompose()

        # 移除广告元素
        _remove_ads(soup)

        # 提取标题（在移除噪音之前）
        title = ''
        if soup.find('title'):
            title = soup.find('title').get_text(strip=True)
        elif soup.find('h1'):
            title = soup.find('h1').get_text(strip=True)

        # 先提取正文（在移除噪音之前）
        content_text = _extract_main_content(soup)

        # 如果提取失败或内容太短，尝试移除噪音后再提取
        if len(content_text) < 100:
            _remove_noise_sections(soup)
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

    # 裁剪内容边界（移除导航和结尾噪音）
    content_text = _trim_content_boundaries(content_text)

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


def _remove_noise_sections(soup):
    """移除无关区域（评论、相关文章、推荐、导航等）"""
    # 要移除的无关区域选择器
    noise_selectors = [
        # 评论区域
        '.comment', '.comments', '.comment-list', '.comment-box',
        '#comments', '#comment', '.reply-list', '.comment-wrap',
        # 相关文章/推荐
        '.related', '.related-post', '.related-article', '.related-news',
        '.recommend', '.recommend-list', '.tuijian', '.hot-recommend',
        '.similar', '.similar-article', '.related-wrap',
        # CSDN 特定推荐
        '.recommend-box', '.recommend-item', '.blog-recommend',
        '.article-bar-flex', '.article-footer-right',
        '#recommend-right', '.recommend-right',
        # 分享/社交
        '.share', '.share-box', '.social-share', '.share-buttons',
        '.social', '.social-links', '.share-wrap',
        # 侧边栏/小工具
        '.sidebar', '.widget', '.side-widget', '.sidebar-widget',
        '.widget-area', '.sidebar-box', '.aside',
        # 导航/菜单/顶栏
        '.nav', '.navbar', '.navigation', '.menu', '.nav-menu',
        '.breadcrumb', '.crumb', '.top-nav', '.header-nav',
        '.nav-wrap', '.nav-box', '.nav-list',
        # 页脚信息
        '.footer-nav', '.footer-links', '.footer-info', '.copyright',
        '.site-info', '.site-links', '.footer', '#footer',
        # 登录/注册/会员
        '.login', '.register', '.login-box', '.user-panel',
        '.member', '.member-login', '.vip', '.user-box',
        # 标签/分类
        '.tags', '.tag-list', '.category-list', '.cate-list',
        # 作者信息
        '.author', '.author-info', '.author-box', '.author-wrap',
        # CSDN 作者栏
        '.profile-intro', '.tool-box', '.operating',
        # 上下篇
        '.post-nav', '.nav-links', '.prev-next',
        # 排行榜/热门
        '.ranking', '.hot-list', '.popular', '.top-list',
        '.month-rank', '.week-rank', '.click-rank',
        # 广告位
        '.ad-box', '.banner-box', '.ad-wrap',
        # 其他噪音
        '.search-box', '.search-form', '.toolbar', '.tools',
        '.meta', '.post-meta', '.article-meta',  # 文章元信息通常噪音
        # CSDN 特定噪音
        '.article-info-box', '.tit', '.more-toolbox',
        '.article-copyright', '.original-info',
        '.vip-cau', '.cau', '.hide-article-box',
    ]

    # ID选择器
    noise_ids = [
        'comments', 'comment', 'sidebar', 'footer', 'header',
        'nav', 'navbar', 'menu', 'related', 'recommend',
        'share', 'social', 'login', 'register', 'member',
        'ranking', 'hot', 'popular', 'top-list',
    ]

    for selector in noise_selectors:
        for elem in soup.select(selector):
            try:
                elem.decompose()
            except:
                pass

    # 移除特定ID的元素
    for id_name in noise_ids:
        elem = soup.find(id=id_name)
        if elem:
            try:
                elem.decompose()
            except:
                pass


def _trim_content_boundaries(text):
    """智能裁剪内容边界，移除开头导航和结尾噪音"""
    if not text:
        return text

    # 开头噪音模式（导航栏、频道列表等）
    start_noise_patterns = [
        # 移动支付网：匹配从开头到"来源：移动支付网"之前的内容
        (r'^资讯\s+焦点\s+业界\s+视角.*?会员登录\s+会员注册\s+', ''),
        (r'^[\s]*(?:首页|主页|Home)\s+', ''),
        # 登录注册区域
        (r'^[\s]*会员登录\s+会员注册\s+', ''),
        # 多个频道名连排（至少3个）
        (r'^[\s]*[\u4e00-\u9fa5]{2,4}\s+[\u4e00-\u9fa5]{2,4}\s+[\u4e00-\u9fa5]{2,4}\s+', ''),
    ]

    for pattern, replacement in start_noise_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 特别处理：移除开头的频道导航文字（移动支付网特有）
    nav_match = re.match(r'^([\u4e00-\u9fa5]+\s+){5,}投稿\s+会员登录\s+会员注册\s+', text)
    if nav_match:
        text = text[nav_match.end():]

    # 处理部分导航栏残留
    nav_match2 = re.match(r'^([\u4e00-\u9fa5]+\s+){4,}投稿\s+', text)
    if nav_match2:
        text = text[nav_match2.end():]

    # 处理更短的导航栏残留
    nav_match3 = re.match(r'^([\u4e00-\u9fa5]{2,4}\s+){4,}', text)
    if nav_match3 and nav_match3.end() < 100:
        text = text[nav_match3.end():]

    # CSDN 特殊处理：移除开头的文章元信息（只在开头位置）
    # 先尝试匹配完整的 CSDN 元信息块（标题 + 发布 + 原创 + 版权 + 标签）
    csdn_full_meta = re.match(
        r'^[\u4e00-\u9fa5a-zA-Z0-9\s]{5,60}\s*\n'  # 标题行
        r'\s*\n'  # 空行
        r'(最新推荐文章.*?发布\s*\n)?'  # 推荐文章发布时间（可选）
        r'\s*\n'  # 空行
        r'(原创\s*\n)?'  # 原创（可选）
        r'(于\s*[\d\-:]+\s+发布\s*\n)?'  # 发布时间（可选）
        r'(\s*[·\.\d]+\s*\n)*'  # 数字/符号行
        r'\s*\n'  # 空行
        r'(版权声明.*?本声明\s*\n)?'  # 版权声明（可选）
        r'\s*\n'  # 空行
        r'(文章标签[：:]\s*\n)?'  # 文章标签（可选）
        r'(\s*#[\u4e00-\u9fa5a-zA-Z]+\s*\n)+'  # 标签行
        r'\s*\n',  # 空行
        text, re.MULTILINE
    )
    if csdn_full_meta and csdn_full_meta.end() < 500:
        text = text[csdn_full_meta.end():]

    # 如果没匹配到完整的，尝试单独匹配版权声明+标签（在开头位置）
    if text.startswith('版权声明') or text.startswith('文章标签'):
        csdn_meta_simple = re.match(
            r'^版权声明.*?本声明\s*\n'
            r'\s*\n'
            r'文章标签[：:]\s*\n'
            r'(\s*#[\u4e00-\u9fa5a-zA-Z]+\s*\n)+'
            r'\s*\n',
            text, re.MULTILINE
        )
        if csdn_meta_simple:
            text = text[csdn_meta_simple.end():]

        # 单独匹配文章标签
        csdn_tags = re.match(
            r'^文章标签[：:]\s*\n'
            r'(\s*#[\u4e00-\u9fa5a-zA-Z]+\s*\n)+'
            r'\s*\n',
            text, re.MULTILINE
        )
        if csdn_tags:
            text = text[csdn_tags.end():]

    # 中间噪音模式（弹窗广告、VIP推广等）
    mid_noise_patterns = [
        # CSDN VIP 弹窗广告
        (r'\n\s*确定要放弃本次机会\?.*?立即使用\s*', ''),
        (r'\n\s*福利倒计时.*?立减.*?普通VIP.*?立即使用\s*', ''),
        (r'\n\s*¥\s*', ''),
        (r'\n\s*普通VIP年卡可用\s*', ''),
        # 作者操作按钮
        (r'\n\s*潘铭允.*?\n', ''),  # 作者名（需要更精确的匹配）
        (r'\n\s*关注\s+关注\s+', ''),
        (r'\n\s*\d+\s+点赞\s+', ''),
        (r'\n\s*踩\s+', ''),
        (r'\n\s*\d+\s+收藏\s+', ''),
        (r'\n\s*觉得还不错\?.*?一键收藏\s*', ''),
        (r'\n\s*0\s+评论\s+', ''),
        (r'\n\s*分享\s+复制链接.*?举报\s+', ''),
        (r'\n\s*扫一扫\s+', ''),
        (r'\n\s*举报\s+举报\s*', ''),
    ]

    for pattern, replacement in mid_noise_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE | re.DOTALL)

    # 结尾噪音模式（相关文章、排行榜、版权信息等）
    end_noise_patterns = [
        (r'\s*相关文章\s.*?$', ''),
        (r'\s*月点击排行\s.*?$', ''),
        (r'\s*关于本站\s.*?$', ''),
        (r'\s*版权声明\s.*?$', ''),
        (r'\s*Copyright\s.*?$', ''),
        (r'\s*(?:粤ICP备|京ICP备).*?$', ''),
        (r'\s*(?:还没有人评论|请先登录).*?$', ''),
        (r'\s*分享\s.*?收藏\s.*?$', ''),
        (r'\s*\d+条评论\s.*?$', ''),
        (r'\s*阅读原文\s*$', ''),
        # 移动支付网特有结尾
        (r'\s*深圳市.*?信息技术产业园.*?$', ''),
        (r'\s+阅读原文\s+.*?$', ''),
        # CSDN 特有结尾
        (r'\s*参与评论\s.*?$', ''),
        (r'\s*您还未登录.*?后发表或查看评论\s*$', ''),
        (r'\s*热门推荐\s.*?$', ''),
        (r'\s*最新发布\s.*?$', ''),
        (r'\s*关于我们\s.*?$', ''),
        (r'\s*招贤纳士\s.*?$', ''),
        (r'\s*商务合作\s.*?$', ''),
        (r'\s*寻求报道\s.*?$', ''),
        (r'\s*400-660-0108\s.*?$', ''),
        (r'\s*kefu@csdn\.net\s.*?$', ''),
        (r'\s*在线客服\s.*?$', ''),
        (r'\s*工作时间\s.*?$', ''),
        (r'\s*公安备案号.*?$', ''),
        # CSDN 推荐文章（从第一个推荐文章标题开始）
        (r'\s*\n\s*[\u4e00-\u9fa5a-zA-Z0-9_]+的博客\s+\d{2}-\d{2}\s+\d+\s*$', ''),
        # CSDN VIP弹窗广告截断
        (r'\n\s*确定要放弃本次机会.*?$', ''),
        (r'\n\s*点赞\d+\s+收藏\d+\s+评论举报\s*$', ''),
        (r'\n\s*点赞\d+\s+收藏\d+\s+踩\s+评论\s*$', ''),
    ]

    for pattern, replacement in end_noise_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE | re.DOTALL)

    # CSDN 特殊处理：从"参与评论"或推荐文章开始截断
    # 只有在文章内容足够长时才截断（避免误截断开头）
    if len(text) > 500:
        comment_marker = re.search(r'\n\s*参与评论\s', text)
        if comment_marker and comment_marker.start() > 300:  # 确保不在开头附近
            text = text[:comment_marker.start()]

        # 从博客名+日期格式的推荐文章开始截断（如 "喵手的博客 04-06 336"）
        recommend_pattern = re.search(r'\n\s*[\u4e00-\u9fa5a-zA-Z0-9_]+的博客\s+\d{2}-\d{2}\s+\d+', text)
        if recommend_pattern and recommend_pattern.start() > 500:  # 确保不在文章开头附近
            text = text[:recommend_pattern.start()]

    # 清理Unicode图标字符残留（icon font）
    text = re.sub(r'[\ue600-\ue900]+', '', text)

    return text.strip()


def _extract_main_content(soup):
    """从BeautifulSoup对象中提取主要内容"""
    content_selectors = [
        # 知乎（优先级最高）
        '.Post-RichText', '.RichText', '.RichContent', '.RichContent-inner',
        '[class*="RichText"]', '.Post-Main',
        # CSDN
        '#article_content', '#content_views', '.markdown_views',
        '.htmledit_views', '.article-content-box',
        # 博客园
        '.postBody', '.post-body', '#cnblogs_post_body',
        # 通用
        'article', 'main', '.content', '.article', '.post',
        '.entry-content', '.post-content', '#content',
        '.article-content', '.detail', '.body', '.text',
        '.main-content', '.lemma-summary', '.para',
    ]

    # 收集所有匹配的元素，选择文本最长的
    all_candidates = []
    for selector in content_selectors:
        elements = soup.select(selector)
        for elem in elements:
            text_len = len(elem.get_text())
            if text_len > 50:  # 至少要有50字符
                all_candidates.append((elem, text_len, selector))

    if all_candidates:
        # 按文本长度排序，选择最长的
        all_candidates.sort(key=lambda x: x[1], reverse=True)
        best_elem, best_len, best_selector = all_candidates[0]
        return _extract_text_with_paragraphs(best_elem)

    if soup.find('body'):
        return _extract_text_with_paragraphs(soup.find('body'))

    return ''


def _extract_text_with_paragraphs(element):
    """从元素中提取文本，保留段落结构"""
    # 先处理行内元素，确保文本连贯
    inline_tags = ['span', 'a', 'strong', 'b', 'em', 'i', 'u', 'mark', 'small', 'sub', 'sup']
    for tag_name in inline_tags:
        for tag in element.find_all(tag_name):
            tag.unwrap()  # 移除标签但保留内容

    # 处理块级元素，在元素前后插入特殊换行标记
    block_tags = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                  'li', 'article', 'section', 'blockquote', 'pre']

    # 使用 NavigableString 插入换行标记（这样 get_text 会保留）
    from bs4 import NavigableString

    for tag_name in block_tags:
        for tag in element.find_all(tag_name):
            # 检查是否有实际文本内容
            text = tag.get_text(strip=True)
            if text:
                # 在块级元素后插入换行
                tag.insert_after(NavigableString('\n\n'))
                if tag_name not in ['br']:
                    # 在块级元素前插入换行
                    tag.insert_before(NavigableString('\n'))

    # 处理 br 标签
    for tag in element.find_all('br'):
        tag.insert_after(NavigableString('\n'))

    # 获取文本，不strip，保留换行
    text = element.get_text()

    # 清理多余空白，但保留换行
    text = re.sub(r'[ \t]+', ' ', text)  # 合并空格和制表符
    text = re.sub(r'\n{3,}', '\n\n', text)  # 最多保留两个换行
    text = re.sub(r' *\n *', '\n', text)  # 清理换行前后的空格

    # 清理开头的换行和空格
    text = re.sub(r'^[\n\s]+', '', text)

    return text.strip()


def smart_clean_text(text):
    """智能清理文本：合并多余空白，移除无效字符"""
    if not text:
        return ''

    # 移除零宽度字符
    text = re.sub(r'[\u200b-\u200f\u2028-\u202f\ufeff\u00ad]', '', text)

    # 替换 HTML 特殊空格为普通空格
    text = text.replace('\xa0', ' ')
    # 移除可能导致编码问题的货币符号（VIP广告）
    text = re.sub(r'[¥￥\xa5]', '', text)
    # 各种空格字符 -> 普通空格
    text = re.sub(r'[\u2002-\u200a]', ' ', text)

    # 清理多余空白，保留已有的换行
    text = re.sub(r'[ \t]+', ' ', text)  # 合并空格和制表符
    text = re.sub(r'\n{3,}', '\n\n', text)  # 最多保留两个换行
    text = re.sub(r' *\n *', '\n', text)  # 清理换行前后的空格

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

    # 知乎特殊处理：知乎页面中的"安全验证"通常是登录弹窗，不是反爬
    # 真正的反爬是"知乎安全中心"页面，URL包含 security.zhihu.com
    if 'zhihu.com' in url_lower:
        # 检查是否是知乎真正的安全验证页面
        if 'security.zhihu.com' in url_lower:
            return True
        # 检查是否是知乎的验证码页面（滑块验证）
        if 'signin?next' in url_lower or 'captcha' in url_lower:
            return True
        # 知乎正常文章页面，即使包含"安全验证"字样（登录弹窗），也不算反爬
        # 只检查真正的反爬特征
        if '访问过于频繁' in html_lower or '人机验证' in html_lower:
            return True
        # 知乎文章页面，不算反爬
        if 'zhuanlan.zhihu.com' in url_lower or 'zhihu.com/question' in url_lower:
            return False
        # 其他知乎页面，检查是否有真正的反爬
        return False

    # 百度相关的反爬检测
    if 'baidu.com' in url_lower:
        if 'wappass.baidu.com' in url_lower or '百度安全验证' in html_lower:
            return True

    # 通用反爬检测（排除知乎）
    anti_patterns = [
        '验证码',
        '请输入验证码', '访问过于频繁',
        '滑块验证',
        'security check', 'cloudflare',
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