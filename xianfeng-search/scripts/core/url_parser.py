#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - URL解析
"""

import os
import re
import hashlib
from typing import Dict

# 导入配置
from .config import JSON_CACHE_DIR, ALLOWED_DOMAIN_SUFFIXES


def parse_feishu_url(url: str) -> Dict:
    """
    解析飞书URL

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

    # 去除两端可能的引号
    url = url.strip().strip('"').strip("'")

    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url

    match = re.match(r'(https?://[^/]+)', url)
    if match:
        result['domain'] = match.group(1).rstrip('/')

    # 提取类型和ID
    patterns = [
        (r'/drive/folder/([^/?]+)', 'folder'),
        (r'/docx/([^/?]+)', 'docx'),
        (r'/wiki/([^/?]+)', 'wiki'),
        (r'/sheet/([^/?]+)', 'sheet'),
        (r'/sheets/([^/?]+)', 'sheet'),
    ]

    for pattern, type_name in patterns:
        match = re.search(pattern, url)
        if match:
            result['type'] = type_name
            result['id'] = match.group(1)
            return result

    if '/drive' in url and not result['id']:
        result['type'] = 'drive'
        result['id'] = 'root'

    return result


def extract_doc_id(url: str) -> str:
    """从URL提取文档ID"""
    match = re.search(r'/docx/([^/?]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'/sheets/([^/?]+)', url)
    if match:
        return match.group(1)
    return ''


def get_folder_cache_id(domain: str, folder_id: str) -> str:
    """生成文件夹缓存ID"""
    if folder_id and folder_id != 'root':
        return folder_id

    domain_hash = hashlib.md5(domain.encode()).hexdigest()[:12]
    return f"root_{domain_hash}"


def get_cache_path_for_folder(domain: str, folder_id: str) -> str:
    """获取文件夹缓存文件路径"""
    cache_id = get_folder_cache_id(domain, folder_id)
    return os.path.join(JSON_CACHE_DIR, f"{cache_id}.json")


def validate_domain(domain: str) -> bool:
    """验证域名是否在允许列表中"""
    if not domain:
        return False

    domain = domain.lower()

    for suffix in ALLOWED_DOMAIN_SUFFIXES:
        if suffix in domain:
            return True

    if domain.startswith('http://') or domain.startswith('https://'):
        return True

    return False