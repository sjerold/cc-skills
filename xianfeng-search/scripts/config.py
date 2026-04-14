#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 配置管理

Chrome相关配置在feishu_navigator.py中定义（端口9225，复制Chrome配置启动独立实例）
"""

import os
import sys
import re
import hashlib

# ============ 飞书配置 ============

# 默认飞书域名（可从环境变量或命令行覆盖）
DEFAULT_DOMAIN = os.environ.get('XIANFENG_DOMAIN', None)

# 允许的域名后缀（白名单验证）
ALLOWED_DOMAIN_SUFFIXES = [
    '.feishu.cn',
    '.larksuite.com',
    '.larkoffice.com',
]

# ============ 缓存配置 ============

# 缓存目录放在Downloads下
CACHE_DIR = os.path.expanduser("~/Downloads/衔风云文档缓存")
JSON_CACHE_DIR = os.path.join(CACHE_DIR, "目录结构")  # JSON缓存目录
CACHE_MAX_AGE_HOURS = 24 * 7  # 缓存有效期（7天）

# MD文件保存目录（抓取的内容）
CONTENT_DIR = os.path.join(CACHE_DIR, "文档内容")

# ============ 文件类型过滤 ============

# 跳过缓存的文件类型（PPT、图片等）
SKIP_FETCH_EXTENSIONS = [
    '.ppt', '.pptx',      # PowerPoint
    '.key',                # Keynote
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',  # 图片
    '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv',  # 视频
    '.mp3', '.wav', '.flac', '.aac',  # 音频
    '.zip', '.rar', '.7z', '.tar', '.gz',  # 压缩包
    '.exe', '.dmg', '.apk', '.ipa',  # 可执行文件
]

# 支持抓取的文档类型
SUPPORTED_DOC_EXTENSIONS = [
    '.doc', '.docx',      # Word
    '.pdf',               # PDF
    '.txt', '.md',        # 文本
    '.xls', '.xlsx',      # Excel
    '.html', '.htm',      # 网页
]

# 在线文档类型（飞书在线文档没有扩展名）
ONLINE_DOC_TYPES = ['docx', 'sheet', 'wiki', 'doc']

# ============ 超时配置 ============

LOGIN_WAIT_TIMEOUT = 300  # 登录等待超时（5分钟）
PAGE_LOAD_TIMEOUT = 30    # 页面加载超时（秒）
CONTENT_WAIT_TIMEOUT = 10 # 内容等待超时（秒）
SCROLL_WAIT_TIME = 0.5    # 滚动等待时间（秒）

# ============ 搜索配置 ============

DEFAULT_RESULT_LIMIT = 50  # 默认结果数量限制
MIN_MATCH_SCORE = 0.3      # 最低匹配分数

# ============ 输出配置 ============

DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Downloads/xianfeng_search")

# ============ CLI配置 ============

CLI_DESCRIPTION = "衔风 - 飞书文档本地搜索工具"
CLI_EPILIG = """
示例:
  python xianfeng_search_cli.py 扫描 -u https://xxx.feishu.cn/drive/folder/xxx
  python xianfeng_search_cli.py 缓存 -u https://xxx.feishu.cn/drive/folder/xxx
  python xianfeng_search_cli.py 搜索 关键词
  python xianfeng_search_cli.py --status
"""
CLI_DEFAULT_LIMIT = 50
CLI_COMMANDS = {
    'scan': '扫描',
    'cache': '缓存',
    'search': '搜索',
    'debug': '调试',
}

# ============ 排除目录 ============

SCAN_EXCLUDE_PATTERNS = [
    '回收站',
    'Trash',
    '已删除',
    '.trash',
]

# ============ User Agent ============

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'


# ============ URL解析 ============

def parse_feishu_url(url: str) -> dict:
    """
    解析飞书URL，提取域名、类型、ID等信息

    Args:
        url: 飞书URL

    Returns:
        {
            'domain': 'https://xxx.com',
            'type': 'folder' | 'docx' | 'wiki' | 'sheet' | 'drive',
            'id': '文件夹或文档ID',
            'original_url': '原始URL'
        }
    """
    result = {
        'domain': '',
        'type': 'unknown',
        'id': '',
        'original_url': url
    }

    if not url:
        return result

    # 确保URL有协议
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url

    # 提取域名
    match = re.match(r'(https?://[^/]+)', url)
    if match:
        result['domain'] = match.group(1).rstrip('/')

    # 提取类型和ID
    # 格式1: /drive/folder/{id}
    match = re.search(r'/drive/folder/([^/?]+)', url)
    if match:
        result['type'] = 'folder'
        result['id'] = match.group(1)
        return result

    # 格式2: /docx/{id}
    match = re.search(r'/docx/([^/?]+)', url)
    if match:
        result['type'] = 'docx'
        result['id'] = match.group(1)
        return result

    # 格式3: /wiki/{id}
    match = re.search(r'/wiki/([^/?]+)', url)
    if match:
        result['type'] = 'wiki'
        result['id'] = match.group(1)
        return result

    # 格式4: /sheet/{id}
    match = re.search(r'/sheet/([^/?]+)', url)
    if match:
        result['type'] = 'sheet'
        result['id'] = match.group(1)
        return result

    # 格式5: /drive/ (根目录)
    if '/drive' in url and not result['id']:
        result['type'] = 'drive'
        result['id'] = 'root'

    return result


def get_folder_cache_id(domain: str, folder_id: str) -> str:
    """
    生成文件夹缓存的标准ID

    Args:
        domain: 域名
        folder_id: 文件夹ID

    Returns:
        缓存ID (用于缓存文件名)
    """
    # 使用文件夹ID作为主要标识
    if folder_id and folder_id != 'root':
        return folder_id

    # 如果没有文件夹ID，使用域名hash
    domain_hash = hashlib.md5(domain.encode()).hexdigest()[:12]
    return f"root_{domain_hash}"


def get_cache_path_for_folder(domain: str, folder_id: str) -> str:
    """
    获取文件夹的缓存文件路径

    Args:
        domain: 域名
        folder_id: 文件夹ID

    Returns:
        缓存文件完整路径
    """
    cache_id = get_folder_cache_id(domain, folder_id)
    return os.path.join(JSON_CACHE_DIR, f"{cache_id}.json")


def validate_domain(domain: str) -> bool:
    """验证域名是否在允许列表中或符合私有化部署格式"""
    if not domain:
        return False

    domain = domain.lower()

    # 允许的公网域名
    for suffix in ALLOWED_DOMAIN_SUFFIXES:
        if suffix in domain:
            return True

    # 私有化部署域名（通常是内网域名）
    # 允许 http:// 或 https:// 开头的任何域名
    if domain.startswith('http://') or domain.startswith('https://'):
        return True

    return False