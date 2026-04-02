#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页文章抓取脚本
支持链接发现、内容抓取、MD保存、增量更新

功能：
1. 从源页面发现文章链接
2. 增量过滤已抓取URL
3. 使用Playwright渲染动态页面
4. 智能提取正文内容
5. 保存为规范的Markdown文件

改动：
- 使用common模块统一Chrome管理（端口9222）
"""

import sys
import json
import io
import argparse
import os
import time
import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

# 确保 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加common模块路径
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_SCRIPTS_DIR)
_PLUGINS_DIR = os.path.dirname(_PLUGIN_DIR)
COMMON_PATH = os.path.join(_PLUGINS_DIR, 'common', 'scripts')
sys.path.insert(0, COMMON_PATH)

# ============ 依赖检查 ============

try:
    import requests
except ImportError:
    print(json.dumps({'error': '请安装 requests: pip install requests'}, ensure_ascii=False))
    sys.exit(1)

HAS_BS4 = False
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    pass

HAS_PLAYWRIGHT = False
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    pass

# 导入common模块
try:
    from chrome_manager import (
        get_browser,
        get_page,
        close_browser,
        is_chrome_debug_running,
        start_debug_chrome
    )
    HAS_CHROME_MANAGER = True
except ImportError as e:
    print(f"无法导入chrome_manager: {e}", file=sys.stderr)
    HAS_CHROME_MANAGER = False


# ============ 配置 ============

# 默认保存目录
DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser('~'), 'Downloads', 'web_article_fetcher')

# 状态文件名
STATE_FILE_NAME = '.fetched_urls.json'

# User-Agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

# 默认文章链接选择器
ARTICLE_LINK_SELECTORS = [
    'a[href*="/article/"]',
    'a[href*="/news/"]',
    'a[href*=".html"]',
    'a[href*="/detail/"]',
    'a[href*="/content/"]',
    '.article-list a',
    '.news-list a',
    '.post-list a',
    'article a',
    'main a',
]

# 站点预设配置
SITE_CONFIGS = {
    'mpaypass.com.cn': {
        'name': '移动支付网',
        'link_selectors': ['a[href*="/news/"]', 'a[href*="/article/"]'],
        'content_selectors': ['.news-content', '.article-body', 'article'],
        'time_selector': '.pub-time',
    },
    '36kr.com': {
        'name': '36氪',
        'link_selectors': ['a[href*="/p/"]'],
        'content_selectors': ['.article-content', 'article'],
    },
}

# 网站别名映射（中文名 -> URL）
SITE_ALIASES = {
    '移动支付网': 'https://www.mpaypass.com.cn/',
    'mpaypass': 'https://www.mpaypass.com.cn/',
    '36氪': 'https://www.36kr.com/',
    '36kr': 'https://www.36kr.com/',
}

# 反爬检测模式
ANTI_CRAWL_PATTERNS = [
    '百度安全验证', '安全验证', '验证码', 'captcha',
    'wappass.baidu.com', '请输入验证码', '访问过于频繁',
    '人机验证', '请完成安全验证', 'robots检测'
]


# ============ 模块1: 链接发现 ============

def get_site_config(url):
    """根据URL获取站点配置"""
    domain = urlparse(url).netloc
    for site_domain, config in SITE_CONFIGS.items():
        if site_domain in domain:
            return config
    return None


def discover_links(source_url, html, config=None):
    """从网页中发现文章链接

    Args:
        source_url: 源页面URL
        html: 页面HTML内容
        config: 可选站点配置

    Returns:
        list[dict]: 发现的链接列表
    """
    if not HAS_BS4:
        print("需要BeautifulSoup4来解析链接", file=sys.stderr)
        return []

    soup = BeautifulSoup(html, 'html.parser')
    source_domain = urlparse(source_url).netloc

    # 使用站点配置的选择器或默认选择器
    if config and 'link_selectors' in config:
        selectors = config['link_selectors']
    else:
        selectors = ARTICLE_LINK_SELECTORS

    discovered = []

    # 首先移除广告区域，避免提取广告链接
    ad_area_selectors = [
        '.ad', '.ads', '.advertisement', '.ad-wrapper', '.ad-container',
        '.banner', '.sponsor', '.promoted', '.recommend-ad',
        '#ad', '#ads', '#advertisement',
        '.sidebar-ad', '.footer-ad', '.header-ad',
        '.google-ad', '.baidu-ad', '.ssp-ad',
        '[class*="ad-"]', '[class*="-ad"]', '[id*="ad-"]',
        '.hot-recommend', '.tuijian', '.recommend-list:not(.article-list)',
        '.related-ad', '.sidebar-widget:not(.article-widget)',
    ]
    for selector in ad_area_selectors:
        for elem in soup.select(selector):
            elem.decompose()

    # 移除导航、侧边栏等非内容区域
    non_content_selectors = [
        'nav', 'header nav', 'footer nav',
        '.navbar', '.navigation', '.menu', '.nav-menu',
        '.sidebar:not(.article-sidebar)', '.widget:not(.article-widget)',
        '.footer-links', '.header-links', '.site-links',
        '.social-share', '.share-buttons', '.social-links',
        '.comment-box', '.comments-area',  # 评论区域链接通常是用户头像等
        '.login-box', '.register-box', '.user-panel',
    ]
    for selector in non_content_selectors:
        for elem in soup.select(selector):
            elem.decompose()

    # 提取所有匹配的链接（仅在剩余的内容区域中）
    for selector in selectors:
        for link in soup.select(selector):
            href = link.get('href', '')
            if not href:
                continue

            # 构建完整URL
            full_url = urljoin(source_url, href)

            # 获取链接文本作为标题
            title = link.get_text(strip=True)

            # 获取链接周围的上下文（用于判断是否在广告推荐区域）
            parent_classes = []
            for parent in link.parents:
                if parent.get('class'):
                    parent_classes.extend(parent.get('class'))
                if parent.name in ['aside', 'footer', 'header'] and parent.name != 'main':
                    # 链接在非正文区域，跳过
                    break

            # 过滤链接
            if filter_article_link(full_url, title, source_domain, parent_classes):
                discovered.append({
                    'url': full_url,
                    'title': title,
                    'source_url': source_url,
                })

    # 去重
    seen = set()
    unique = []
    for item in discovered:
        if item['url'] not in seen:
            seen.add(item['url'])
            unique.append(item)

    # 按标题长度排序，优先保留标题完整的链接（更可能是真实文章）
    unique.sort(key=lambda x: len(x.get('title', '')), reverse=True)

    return unique


def filter_article_link(url, title, source_domain, parent_classes=None):
    """过滤链接是否为有效文章链接

    Args:
        url: 链接URL
        title: 链接文本
        source_domain: 源页面域名
        parent_classes: 链接父元素的class列表（用于判断是否在广告区域）

    Returns:
        bool: True表示是有效文章链接
    """
    if parent_classes is None:
        parent_classes = []

    # 必须过滤：非HTTP链接
    if not url.startswith(('http://', 'https://')):
        return False

    # 必须过滤：外部链接（不同域名）
    link_domain = urlparse(url).netloc
    if link_domain != source_domain:
        return False

    # 必须过滤：纯锚点链接（页面内跳转，无实际URL）
    if url.startswith('#'):
        return False

    # 过滤：如果锚点前的URL与当前页面相同（同页面跳转）
    if '#' in url:
        base_url = url.split('#')[0]
        # 只有当锚点前的URL是空或与源URL相同时，才过滤
        # 完整URL带锚点（如 https://example.com/news/123#comments）应保留
        parsed = urlparse(url)
        if not base_url or (parsed.path == '' or parsed.path == '/'):
            return False

    # 必须过滤：导航链接
    nav_patterns = [
        '/login', '/register', '/signin', '/signup',
        '/about', '/contact', '/help', '/faq',
        '/privacy', '/terms', '/sitemap', '/search',
        'javascript:', 'mailto:', 'tel:',
        '/category/', '/tag/', '/tags/',  # 分类和标签页通常是列表页，不是文章
    ]
    for pattern in nav_patterns:
        if pattern in url.lower():
            return False

    # 必须过滤：分页链接
    pagination_patterns = [
        'page=', 'pn=', 'p=', '/page/', '/pages/',
        '/list/', '/index/', '/archive/',
    ]
    for pattern in pagination_patterns:
        if pattern in url.lower():
            return False

    # 必须过滤：广告链接（URL层面）
    ad_url_patterns = [
        'ad', 'ads', 'advert', 'advertisement',
        'promo', 'sponsor', 'promoted', 'banner',
        'click', 'redirect', 'track', 'affiliate',
        'doubleclick', 'googlesyndication', 'baiduad',
        '/go/', '/jump/', '/link/', '/out/',
    ]
    url_lower = url.lower()
    for pattern in ad_url_patterns:
        if pattern in url_lower:
            return False

    # 必须过滤：父元素包含广告相关class
    ad_class_patterns = [
        'ad', 'ads', 'advert', 'advertisement', 'banner',
        'sponsor', 'promo', 'promoted', 'tuijian', 'recommend',
        'hot', 'popular', 'sidebar-widget', 'footer-widget',
        'related-ad', 'google-ad', 'baidu-ad',
    ]
    for cls in parent_classes:
        cls_lower = cls.lower()
        for pattern in ad_class_patterns:
            if pattern in cls_lower:
                return False

    # 必须过滤：标题过短或过长（通常是无效链接）
    if len(title) < 3:  # 太短可能是图标或导航
        return False
    if len(title) > 150:  # 太长可能是整段文本误提取
        return False

    # 必须过滤：标题包含广告关键词
    ad_title_patterns = [
        '广告', '推广', '赞助', '推荐', '热门',
        'AD', '广告位', '招商', '合作',
        '点击查看', '点击下载', '立即购买',
        '了解更多', '查看详情',  # 如果标题是这类按钮文本，通常是广告
    ]
    title_lower = title.lower()
    for pattern in ad_title_patterns:
        if pattern.lower() in title_lower and len(title) < 20:
            # 广告关键词 + 短标题 = 高概率是广告
            return False

    # 优先保留：URL含文章特征
    article_patterns = [
        '/article/', '/news/', '/detail/', '/content/', '/post/',
        '.html', '.htm', '/p/', '/a/', '/doc/',
        '/story/', '/report/', '/feature/',
        '/202', '/201',  # 包含年份通常是新闻文章
    ]
    has_article_pattern = any(pattern in url.lower() for pattern in article_patterns)

    # 优先保留：URL路径深度 >= 2
    path = urlparse(url).path
    path_depth = len([p for p in path.split('/') if p])
    has_depth = path_depth >= 2

    # 优先保留：标题长度适中（标题特征）
    has_title = 5 <= len(title) <= 80

    # 综合判断
    if has_article_pattern:
        return True
    if has_depth and has_title:
        return True
    if has_depth and len(title) >= 3:
        # 路径深度足够且有标题，可能是文章
        return True

    return False


# ============ 模块3: 增量管理 ============

def get_url_hash(url):
    """计算URL的MD5哈希（前8位）"""
    return hashlib.md5(url.encode()).hexdigest()[:8]


def load_state(state_file):
    """加载已抓取状态

    Args:
        state_file: 状态文件路径

    Returns:
        dict: 状态数据
    """
    if not os.path.exists(state_file):
        return {
            'version': '1.0',
            'last_update': None,
            'total_count': 0,
            'urls': {}
        }

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {
            'version': '1.0',
            'last_update': None,
            'total_count': 0,
            'urls': {}
        }


def is_fetched(url, state):
    """检查URL是否已抓取"""
    url_hash = get_url_hash(url)
    return url_hash in state.get('urls', {})


def save_state(state, state_file):
    """保存状态到文件"""
    state['last_update'] = datetime.now().isoformat()
    state['total_count'] = len(state.get('urls', {}))

    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存状态文件失败: {e}", file=sys.stderr)


def add_fetched(state, url, article_info):
    """添加已抓取记录"""
    url_hash = get_url_hash(url)
    state['urls'][url_hash] = {
        'url': url,
        'title': article_info.get('title', ''),
        'fetch_time': datetime.now().isoformat(),
        'file': article_info.get('file', ''),
    }


def clear_state(state_file):
    """清空状态文件"""
    if os.path.exists(state_file):
        try:
            os.remove(state_file)
            print("状态文件已清空", file=sys.stderr)
        except:
            pass


# ============ 模块4: 内容抓取 ============

def fetch_static(url, timeout=15):
    """静态抓取网页内容"""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            content_type = response.headers.get('content-type', '')
            if 'charset=' in content_type:
                response.encoding = content_type.split('charset=')[-1].split(';')[0].strip()
            else:
                response.encoding = 'utf-8'

        html = response.text
        return parse_html(html, response.url)

    except Exception as e:
        return {'success': False, 'error': str(e), 'url': url}


def fetch_with_chrome(url, timeout=30, wait_time=2):
    """使用Chrome浏览器抓取网页（通过common模块）

    Args:
        url: 目标URL
        timeout: 超时时间
        wait_time: 等待页面加载时间
    """
    if not HAS_PLAYWRIGHT or not HAS_CHROME_MANAGER:
        return {
            'success': False,
            'error': 'Playwright或chrome_manager未安装',
            'url': url
        }

    browser = None
    try:
        browser = get_browser()
        if not browser:
            return {
                'success': False,
                'error': '无法连接Chrome',
                'url': url
            }

        page = get_page(browser, timeout=timeout * 1000)
        if not page:
            return {
                'success': False,
                'error': '无法创建页面',
                'url': url
            }

        print(f"正在访问: {url[:60]}...", file=sys.stderr)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)

        # 等待页面加载
        time.sleep(wait_time)

        # 等待网络空闲
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        html = page.content()
        final_url = page.url

        result = parse_html(html, final_url)
        result['fetch_type'] = 'chrome_cdp'
        return result

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'url': url
        }
    finally:
        if browser:
            close_browser(browser, keep_running=True)


def check_anti_crawl(html, url):
    """检测是否遇到反爬"""
    for pattern in ANTI_CRAWL_PATTERNS:
        if pattern.lower() in html.lower() or pattern.lower() in url.lower():
            return True
    return False


def parse_html(html, url):
    """解析HTML提取正文"""

    # 检测反爬/验证码页面
    if check_anti_crawl(html, url):
        return {
            'success': False,
            'error': '遇到反爬限制',
            'url': url,
            'anti_crawl': True
        }

    if HAS_BS4:
        soup = BeautifulSoup(html, 'html.parser')

        # 移除无关元素
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript', 'form', 'button']):
            tag.decompose()

        # 提取标题
        title = ''
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)

        # 尝试提取 h1
        h1_tag = soup.find('h1')
        if h1_tag:
            h1_title = h1_tag.get_text(strip=True)
            if h1_title and len(h1_title) > len(title) * 0.5:
                title = h1_title

        # 提取 meta description
        description = ''
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            description = desc_tag.get('content', '')

        # 提取正文
        content_selectors = [
            'article', 'main', '.content', '.article', '.post',
            '.entry-content', '.post-content', '.article-content',
            '#content', '#article', '.main-content', '.text-content',
            '.news-content', '.article-body',
            'body'
        ]

        content_text = ''
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                best_elem = max(elements, key=lambda e: len(e.get_text()))
                content_text = best_elem.get_text(separator='\n', strip=True)
                if len(content_text) > 200:
                    break

        if not content_text:
            content_text = soup.get_text(separator='\n', strip=True)

    else:
        # 简单正则提取
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ''

        desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        description = desc_match.group(1) if desc_match else ''

        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '\n', text)
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r' +', ' ', text)
        content_text = text.strip()

    # 清理文本
    lines = [line.strip() for line in content_text.split('\n') if line.strip()]
    content_text = '\n'.join(lines)

    # 检测内容是否有效
    if len(title) < 2 and len(content_text) < 100:
        return {
            'success': False,
            'error': '页面内容为空或过短，可能被反爬阻止',
            'url': url,
            'anti_crawl': True
        }

    # 截断过长内容
    if len(content_text) > 15000:
        content_text = content_text[:15000] + '\n... (内容已截断)'

    return {
        'success': True,
        'url': url,
        'title': title,
        'description': description,
        'content': content_text,
        'length': len(content_text),
        'fetch_type': 'static'
    }


def smart_fetch(url, use_chrome='auto', timeout=15, wait_time=2):
    """智能抓取：自动判断是否需要使用Chrome

    Args:
        url: 目标URL
        use_chrome: 'auto'=自动判断, 'always'=总是用Chrome, 'never'=仅静态
        timeout: 超时时间
        wait_time: 等待时间
    """
    if use_chrome == 'always':
        return fetch_with_chrome(url, timeout, wait_time)

    if use_chrome == 'never':
        return fetch_static(url, timeout)

    # 自动模式：先尝试静态，如果内容太少或遇到反爬则使用Chrome
    result = fetch_static(url, timeout)

    if result['success']:
        content_len = result.get('length', 0)

        # 如果内容太少或检测到反爬特征，尝试Chrome
        if content_len < 500 or result.get('anti_crawl'):
            if HAS_PLAYWRIGHT and HAS_CHROME_MANAGER:
                chrome_result = fetch_with_chrome(url, timeout, wait_time)
                if chrome_result['success'] and chrome_result.get('length', 0) > content_len * 1.2:
                    return chrome_result

    elif result.get('anti_crawl') and HAS_PLAYWRIGHT and HAS_CHROME_MANAGER:
        # 静态抓取遇到反爬，尝试Chrome
        chrome_result = fetch_with_chrome(url, timeout, wait_time)
        if chrome_result['success']:
            return chrome_result

    return result


# ============ 模块5: MD保存 ============

def sanitize_filename(title):
    """清理文件名中的非法字符"""
    # 替换Windows非法字符
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
    # 替换连续空格和换行
    safe_title = re.sub(r'\s+', '_', safe_title)
    # 限制长度
    return safe_title[:80]


def get_site_name(url):
    """从URL提取站点名称"""
    domain = urlparse(url).netloc
    # 移除www前缀
    domain = re.sub(r'^www\.', '', domain)
    # 取主域名
    parts = domain.split('.')
    if len(parts) >= 2:
        return parts[0]
    return domain


def save_article(article, save_dir, site_name=None):
    """保存文章为Markdown文件

    目录结构：
    save_dir/
    ├── {site_name}/           # 按来源网站分目录
    │   ├── 文章1.md
    │   └── 文章2.md
    ├── 抓取报告.md            # 报告在外层
    └── .fetched_urls.json     # 状态文件

    Args:
        article: 文章数据 {url, title, content, length, fetch_type}
        save_dir: 保存根目录
        site_name: 站点名称

    Returns:
        str: 文件路径
    """
    if not site_name:
        site_name = get_site_name(article.get('url', ''))

    # 文章保存在网站子目录下
    site_dir = os.path.join(save_dir, site_name)
    os.makedirs(site_dir, exist_ok=True)

    # 清理标题：去掉网站名称后缀（如 "-移动支付网"、"移动支付网"等）
    title = article.get('title', 'untitled')
    # 去掉常见的网站后缀模式
    title_clean = re.sub(r'[-_\s]*' + re.escape(site_name) + r'$', '', title, flags=re.IGNORECASE)
    if not title_clean:
        title_clean = title  # 如果清理后为空，保留原标题

    # 生成文件名：文章标题_时间戳
    safe_title = sanitize_filename(title_clean)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{safe_title}_{timestamp}.md"
    filepath = os.path.join(site_dir, filename)

    # 写入文件
    with open(filepath, 'w', encoding='utf-8') as f:
        # 标题
        f.write(f"# {article.get('title', '无标题')}\n\n")

        # 元信息
        f.write(f"- **来源**: {site_name}\n")
        f.write(f"- **URL**: {article.get('url', '')}\n")
        f.write(f"- **抓取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **抓取方式**: {article.get('fetch_type', 'static')}\n")
        f.write(f"- **内��长度**: {article.get('length', 0)} 字符\n\n")

        # 分隔线
        f.write("---\n\n")

        # 正文
        f.write("## 正文内容\n\n")
        f.write(article.get('content', ''))

    return filepath


def generate_report(results, discovered_count, skipped_count, save_dir, source_url, site_name=None):
    """生成抓取报告

    报告保存在根目录，文件列表引用网站子目录下的文章

    Args:
        results: 抓取结果列表
        discovered_count: 发现的链接总数
        skipped_count: 跳过的已抓取链接数
        save_dir: 保存根目录
        source_url: 源页面URL
        site_name: 站点名称
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(save_dir, f"抓取报告_{timestamp}.md")

    success_count = sum(1 for r in results if r.get('success'))
    failed_count = len(results) - success_count
    anti_crawl_count = sum(1 for r in results if r.get('anti_crawl'))

    with open(report_path, 'w', encoding='utf-8') as f:
        # 标题
        f.write(f"# 网页文章抓取报告\n\n")
        f.write(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 抓取概况
        f.write("## 抓取概况\n\n")
        f.write(f"- **源页面**: {source_url}\n")
        f.write(f"- **站点名称**: {site_name or '未知'}\n")
        f.write(f"- **发现链接**: {discovered_count} 条\n")
        f.write(f"- **跳过已抓取**: {skipped_count} 条\n")
        f.write(f"- **实际抓取**: {len(results)} 条\n")
        f.write(f"- **抓取成功**: {success_count} 条\n")
        f.write(f"- **抓取失败**: {failed_count} 条\n")
        if anti_crawl_count > 0:
            f.write(f"- **遇到反爬**: {anti_crawl_count} 条\n")
        f.write("\n")

        # 成功列表
        f.write("## 成功抓取列表\n\n")
        f.write("| 序号 | 标题 | URL | 内容长度 | 抓取方式 |\n")
        f.write("|------|------|-----|----------|----------|\n")
        for i, r in enumerate(results, 1):
            if r.get('success'):
                title = r.get('title', '无标题')[:40]
                url = r.get('url', '')
                length = r.get('length', 0)
                fetch_type = r.get('fetch_type', 'static')
                f.write(f"| {i} | {title} | [链接]({url}) | {length} | {fetch_type} |\n")
        f.write("\n")

        # 失败列表
        if failed_count > 0:
            f.write("## 失败抓取列表\n\n")
            f.write("| 序号 | URL | 错误原因 |\n")
            f.write("|------|-----|----------|\n")
            for i, r in enumerate(results, 1):
                if not r.get('success'):
                    url = r.get('url', '')
                    error = r.get('error', 'Unknown')[:50]
                    anti = " (反爬)" if r.get('anti_crawl') else ""
                    f.write(f"| {i} | {url[:50]} | {error}{anti} |\n")
            f.write("\n")

        # 本地文件列表（引用子目录）
        f.write("## 本地存档文件\n\n")
        if site_name:
            f.write(f"文章保存在: `{site_name}/` 目录下\n\n")
        for r in results:
            if r.get('success') and r.get('file'):
                # 获取相对于save_dir的路径
                rel_path = os.path.relpath(r['file'], save_dir)
                f.write(f"- [{rel_path}]({rel_path})\n")

    return report_path


# ============ 主流程 ============

def fetch_source_page_html(url):
    """获取源页面原始HTML（用于链接发现）

    使用Chrome获取完整HTML以支持动态加载的页面内容
    """
    print(f"获取源页面HTML: {url}", file=sys.stderr)

    # 优先尝试静态获取
    try:
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        html = response.text

        # 检查HTML是否包含足够的链接
        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            links = soup.find_all('a', href=True)
            if len(links) >= 10:
                print(f"静态获取成功，发现 {len(links)} 个链接", file=sys.stderr)
                return html, response.url
    except Exception as e:
        print(f"静态获取失败: {e}", file=sys.stderr)

    # 静态获取失败或链接太少，使用Chrome
    if not HAS_PLAYWRIGHT or not HAS_CHROME_MANAGER:
        print("无法使用Chrome，返回静态HTML", file=sys.stderr)
        try:
            response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=15)
            return response.text, response.url
        except:
            return None, url

    browser = None
    try:
        browser = get_browser()
        if not browser:
            print("无法连接Chrome，使用静态HTML", file=sys.stderr)
            try:
                response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=15)
                return response.text, response.url
            except:
                return None, url

        page = get_page(browser, url=url, timeout=30000)
        if not page:
            return None, url

        # 等待页面加载
        time.sleep(3)

        # 等待网络空闲
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        html = page.content()
        final_url = page.url

        if HAS_BS4:
            soup = BeautifulSoup(html, 'html.parser')
            links = soup.find_all('a', href=True)
            print(f"Chrome获取成功，发现 {len(links)} 个链接", file=sys.stderr)

        return html, final_url

    except Exception as e:
        print(f"Chrome获取失败: {e}", file=sys.stderr)
        return None, url
    finally:
        if browser:
            close_browser(browser, keep_running=True)


def main():
    parser = argparse.ArgumentParser(description='网页文章抓取工具')
    parser.add_argument('url', nargs='?', help='源页面URL或网站别名（如：移动支付网）')
    parser.add_argument('-n', '--limit', type=int, default=20, help='最大抓取数量 (默认20)')
    parser.add_argument('-o', '--output', help='保存目录 (默认 ~/Downloads/web_article_fetcher)')
    parser.add_argument('--full', action='store_true', help='全量抓取（忽略增量状态）')
    parser.add_argument('--json', action='store_true', help='JSON输出')

    args = parser.parse_args()

    # 检查URL
    if not args.url:
        parser.print_help()
        return

    source_url = args.url.strip()

    # 解析网站别名
    if source_url in SITE_ALIASES:
        source_url = SITE_ALIASES[source_url]
        print(f"别名解析: {args.url} -> {source_url}", file=sys.stderr)
    elif not source_url.startswith(('http://', 'https://')):
        # 尝试模糊匹配别名
        matched = None
        for alias, url in SITE_ALIASES.items():
            if alias.lower() in source_url.lower() or source_url.lower() in alias.lower():
                matched = url
                break
        if matched:
            source_url = matched
            print(f"别名解析: {args.url} -> {source_url}", file=sys.stderr)
        else:
            # 自动添加https前缀
            source_url = 'https://' + source_url

    # 设置保存目录
    if args.output:
        save_dir = os.path.expanduser(args.output)
    else:
        save_dir = DEFAULT_OUTPUT_DIR
    os.makedirs(save_dir, exist_ok=True)

    print(f"源页面: {source_url}", file=sys.stderr)
    print(f"保存目录: {save_dir}", file=sys.stderr)
    print(f"最大抓取: {args.limit}", file=sys.stderr)

    # 状态文件
    state_file = os.path.join(save_dir, STATE_FILE_NAME)

    # 全量模式：清空状态
    if args.full:
        clear_state(state_file)

    # 加载状态
    state = load_state(state_file)

    # 1. 获取源页面HTML
    html, final_url = fetch_source_page_html(source_url)
    if not html:
        print("无法获取源页面内容", file=sys.stderr)
        if args.json:
            print(json.dumps({'error': '无法获取源页面', 'url': source_url}, ensure_ascii=False))
        return

    # 2. 发现文章链接
    config = get_site_config(source_url)
    discovered = discover_links(source_url, html, config)
    print(f"发现 {len(discovered)} 个候选链接", file=sys.stderr)

    # 3. 增量过滤
    to_fetch = []
    skipped = 0
    for item in discovered:
        if is_fetched(item['url'], state):
            skipped += 1
        else:
            to_fetch.append(item)

    print(f"跳过 {skipped} 个已抓取链接", file=sys.stderr)
    print(f"待抓取 {len(to_fetch)} 个链接", file=sys.stderr)

    # 限制数量
    to_fetch = to_fetch[:args.limit]

    if not to_fetch:
        print("没有新的文章需要抓取", file=sys.stderr)
        if args.json:
            print(json.dumps({
                'discovered': len(discovered),
                'skipped': skipped,
                'to_fetch': 0,
                'message': '没有新的文章需要抓取'
            }, ensure_ascii=False))
        return

    # 4. 批量抓取
    results = []
    site_name = config.get('name') if config else get_site_name(source_url)

    for i, item in enumerate(to_fetch):
        print(f"抓取 [{i+1}/{len(to_fetch)}]: {item['url'][:50]}...", file=sys.stderr)

        # 请求间隔
        if i > 0:
            time.sleep(1.0)

        result = smart_fetch(item['url'], use_chrome='auto')

        if result.get('success'):
            # 5. 保存MD文件
            filepath = save_article(result, save_dir, site_name)
            result['file'] = filepath
            print(f"  成功: {result.get('title', '')[:30]} ({result.get('length', 0)} 字符)", file=sys.stderr)

            # 更新状态
            add_fetched(state, item['url'], {
                'title': result.get('title'),
                'file': filepath
            })
        else:
            error = result.get('error', 'Unknown')
            anti = " (反爬)" if result.get('anti_crawl') else ""
            print(f"  失败: {error}{anti}", file=sys.stderr)

        results.append(result)

    # 6. 保存状态文件
    save_state(state, state_file)

    # 7. 生成报告
    report_path = generate_report(results, len(discovered), skipped, save_dir, source_url, site_name)
    print(f"\n报告已生成: {report_path}", file=sys.stderr)

    # 统计
    success_count = sum(1 for r in results if r.get('success'))
    print(f"\n抓取完成: {success_count}/{len(results)} 成功", file=sys.stderr)
    if site_name:
        print(f"文章目录: {os.path.join(save_dir, site_name)}", file=sys.stderr)
    print(f"报告文件: {report_path}", file=sys.stderr)

    # 输出
    if args.json:
        output = {
            'source_url': source_url,
            'save_dir': save_dir,
            'discovered': len(discovered),
            'skipped': skipped,
            'to_fetch': len(to_fetch),
            'success': success_count,
            'failed': len(results) - success_count,
            'results': [
                {
                    'url': r.get('url'),
                    'title': r.get('title'),
                    'success': r.get('success'),
                    'length': r.get('length', 0),
                    'file': r.get('file'),
                    'error': r.get('error') if not r.get('success') else None
                }
                for r in results
            ]
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        # 显示结果摘要
        print("\n" + "=" * 60)
        print("抓取结果摘要")
        print("=" * 60)

        for i, r in enumerate(results, 1):
            if r.get('success'):
                title = r.get('title', '无标题')[:40]
                length = r.get('length', 0)
                print(f"{i}. OK {title} ({length} 字符)")
            else:
                url = r.get('url', '')[:40]
                error = r.get('error', 'Unknown')[:30]
                print(f"{i}. FAIL {url} - {error}")

        print("=" * 60)


if __name__ == '__main__':
    main()