#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 配置
"""

import os

# ============ 飞书配置 ============

DEFAULT_DOMAIN = os.environ.get('XIANFENG_DOMAIN', None)

ALLOWED_DOMAIN_SUFFIXES = [
    '.feishu.cn',
    '.larksuite.com',
    '.larkoffice.com',
]

# ============ 缓存配置 ============

CACHE_DIR = os.path.expanduser("~/Downloads/衔风云文档缓存")
JSON_CACHE_DIR = os.path.join(CACHE_DIR, "目录结构")
CACHE_MAX_AGE_HOURS = 24 * 7  # 7天有效期

CONTENT_DIR = os.path.join(CACHE_DIR, "文档内容")

# ============ 文件类型过滤 ============

SKIP_FETCH_EXTENSIONS = [
    '.ppt', '.pptx', '.key',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',
    '.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv',
    '.mp3', '.wav', '.flac', '.aac',
    '.zip', '.rar', '.7z', '.tar', '.gz',
    '.exe', '.dmg', '.apk', '.ipa',
]

ONLINE_DOC_TYPES = ['docx', 'sheet', 'wiki', 'doc']

# ============ 超时配置 ============

LOGIN_WAIT_TIMEOUT = 300  # 5分钟
PAGE_LOAD_TIMEOUT = 30
CONTENT_WAIT_TIMEOUT = 10
SCROLL_WAIT_TIME = 0.5

# ============ 搜索配置 ============

DEFAULT_RESULT_LIMIT = 50
MIN_MATCH_SCORE = 0.3

# ============ 排除目录 ============

SCAN_EXCLUDE_PATTERNS = [
    '回收站',
    'Trash',
    '已删除',
    '.trash',
]