#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 核心模块导出
"""

from .url_parser import (
    parse_feishu_url,
    extract_doc_id,
    get_folder_cache_id,
    get_cache_path_for_folder,
    validate_domain,
)

from .config import (
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
)

__all__ = [
    'parse_feishu_url',
    'extract_doc_id',
    'get_folder_cache_id',
    'get_cache_path_for_folder',
    'validate_domain',
    'DEFAULT_DOMAIN',
    'CACHE_DIR',
    'JSON_CACHE_DIR',
    'CONTENT_DIR',
    'LOGIN_WAIT_TIMEOUT',
    'PAGE_LOAD_TIMEOUT',
    'CONTENT_WAIT_TIMEOUT',
    'DEFAULT_RESULT_LIMIT',
    'MIN_MATCH_SCORE',
    'SKIP_FETCH_EXTENSIONS',
    'ONLINE_DOC_TYPES',
    'SCAN_EXCLUDE_PATTERNS',
    'ALLOWED_DOMAIN_SUFFIXES',
]