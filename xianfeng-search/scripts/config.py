#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 配置管理 (向后兼容模块)

此文件现在只是一个导入桥接，实际实现在 core 模块中。
CLI 相关配置保留在此文件。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 从新模块导入并重新导出
from core import (
    DEFAULT_DOMAIN,
    CACHE_DIR,
    JSON_CACHE_DIR,
    CONTENT_DIR,
    LOGIN_WAIT_TIMEOUT,
    PAGE_LOAD_TIMEOUT,
    CONTENT_WAIT_TIMEOUT,
    DEFAULT_RESULT_LIMIT,
    MIN_MATCH_SCORE,
    SKIP_FETCH_EXTENSIONS,
    ONLINE_DOC_TYPES,
    SCAN_EXCLUDE_PATTERNS,
    ALLOWED_DOMAIN_SUFFIXES,
    parse_feishu_url,
    get_folder_cache_id,
    get_cache_path_for_folder,
    validate_domain,
)

# 从 core.config 导入额外配置
from core.config import CACHE_MAX_AGE_HOURS, SCROLL_WAIT_TIME

# ============ CLI配置 (保留在此) ============

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

__all__ = [
    'DEFAULT_DOMAIN',
    'CACHE_DIR',
    'JSON_CACHE_DIR',
    'CONTENT_DIR',
    'CACHE_MAX_AGE_HOURS',
    'SCROLL_WAIT_TIME',
    'LOGIN_WAIT_TIMEOUT',
    'PAGE_LOAD_TIMEOUT',
    'CONTENT_WAIT_TIMEOUT',
    'DEFAULT_RESULT_LIMIT',
    'MIN_MATCH_SCORE',
    'SKIP_FETCH_EXTENSIONS',
    'ONLINE_DOC_TYPES',
    'SCAN_EXCLUDE_PATTERNS',
    'ALLOWED_DOMAIN_SUFFIXES',
    'CLI_DESCRIPTION',
    'CLI_EPILIG',
    'CLI_DEFAULT_LIMIT',
    'CLI_COMMANDS',
    'parse_feishu_url',
    'get_folder_cache_id',
    'get_cache_path_for_folder',
    'validate_domain',
]