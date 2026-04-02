#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务操作模块 - 扫描、搜索、抓取等核心功能
"""

import os
import sys
import time
import uuid
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEFAULT_RESULT_LIMIT,
    LOGIN_WAIT_TIMEOUT,
    MIN_MATCH_SCORE,
    parse_feishu_url,
    CACHE_DIR,
    CONTENT_DIR,
    SKIP_FETCH_EXTENSIONS,
)
from cache_manager import (
    load_folder_cache,
    save_folder_cache,
    get_all_cache_status,
    flatten_cache,
    get_all_cached_docs,
    find_folder_info_from_parent_cache,
)


def generate_session_id() -> str:
    """生成会话ID"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    short_uuid = uuid.uuid4().hex[:8]
    return f"{timestamp}_{short_uuid}"


def scan_folder(url: str, options: dict) -> dict:
    """
    扫描文件夹

    Args:
        url: 飞书文件夹URL
        options: 选项 (show_browser, login_timeout)

    Returns:
        扫描结果
    """
    from feishu_navigator import FeishuNavigator
    from directory_scanner import DirectoryScanner

    parsed = parse_feishu_url(url)
    domain = parsed['domain']
    folder_id = parsed['id'] if parsed['type'] == 'folder' else 'root'

    # 从父目录缓存中查找文件夹名称和路径
    folder_info = find_folder_info_from_parent_cache(folder_id)
    folder_name = folder_info.get('folder_name', '')
    folder_path = folder_info.get('folder_path', '')

    print(f"域名: {domain}", file=sys.stderr)
    print(f"文件夹ID: {folder_id}", file=sys.stderr)

    result = {
        'success': False,
        'folder_id': folder_id,
        'session_id': generate_session_id(),
        'total': 0,
        'cache_saved': False,
        'errors': []
    }

    navigator = None
    try:
        navigator = FeishuNavigator(domain, headless=not options.get('show_browser', False))

        if not navigator.open_and_wait_login(target_url=url, timeout=options.get('login_timeout', LOGIN_WAIT_TIMEOUT)):
            result['errors'].append('登录失败或超时')
            return result

        time.sleep(2)
        scanner = DirectoryScanner(navigator)
        cache_data = scanner.scan_current_folder(folder_id=folder_id)

        if cache_data:
            # 使用从父缓存找到的名称和路径（如果有）
            if folder_name:
                cache_data['folder_name'] = folder_name
            if folder_path:
                cache_data['folder_path'] = folder_path

            save_folder_cache(folder_id, cache_data)
            flat_docs = flatten_cache(cache_data)
            result['success'] = True
            result['total'] = len(flat_docs)
            result['cache_saved'] = True
            print(f"\n扫描完成: {len(flat_docs)} 个文档", file=sys.stderr)
            print(f"缓存已保存到: {CACHE_DIR}", file=sys.stderr)

    except Exception as e:
        result['errors'].append(str(e))
        print(f"扫描错误: {e}", file=sys.stderr)
    finally:
        if navigator:
            navigator.close()

    return result


def search_local(keyword: str, options: dict) -> dict:
    """
    在本地缓存中搜索

    Args:
        keyword: 搜索关键词
        options: 选项 (limit)

    Returns:
        搜索结果
    """
    print(f"在本地缓存中搜索: {keyword}", file=sys.stderr)

    result = {
        'query': keyword,
        'session_id': generate_session_id(),
        'timestamp': datetime.now().isoformat(),
        'total': 0,
        'results': [],
        'errors': []
    }

    try:
        status = get_all_cache_status()
        all_docs = []

        for cache_info in status.get('caches', []):
            folder_id = cache_info.get('folder_id')
            if folder_id:
                cache_data = load_folder_cache(folder_id)
                if cache_data:
                    docs = flatten_cache(cache_data)
                    for doc in docs:
                        doc['_source_folder'] = cache_info.get('folder_name', '')
                    all_docs.extend(docs)

        if not all_docs:
            result['errors'].append('没有找到缓存，请先使用 --scan 扫描目录')
            return result

        print(f"共有 {len(all_docs)} 个文档在缓存中", file=sys.stderr)

        # 搜索匹配
        matched = _match_docs(all_docs, keyword)

        # 排序并限制数量
        matched.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        matched = matched[:options.get('limit', DEFAULT_RESULT_LIMIT)]

        result['total'] = len(matched)
        result['results'] = matched
        print(f"找到 {result['total']} 个匹配", file=sys.stderr)

    except Exception as e:
        result['errors'].append(str(e))
        print(f"搜索错误: {e}", file=sys.stderr)

    return result


def _match_docs(docs: List[Dict], keyword: str) -> List[Dict]:
    """匹配文档"""
    keyword_lower = keyword.lower()
    matched = []

    for doc in docs:
        name = doc.get('name', '').lower()
        path = doc.get('folder_path', '').lower()

        score = 0
        if keyword_lower == name:
            score = 1.0
        elif keyword_lower in name:
            score = 0.8
        elif keyword_lower in path:
            score = 0.5
        else:
            # 模糊匹配
            kw_chars = list(keyword_lower)
            matched_chars = sum(1 for c in kw_chars if c in name)
            if matched_chars > 0:
                score = matched_chars / len(kw_chars) * 0.3

        if score >= MIN_MATCH_SCORE:
            doc_copy = doc.copy()
            doc_copy['match_score'] = score
            matched.append(doc_copy)

    return matched


def search_online(keyword: str, url: str, options: dict) -> dict:
    """
    在线搜索：重新扫描 → 更新缓存 → 本地搜索

    Args:
        keyword: 搜索关键词
        url: 飞书URL
        options: 选项

    Returns:
        搜索结果
    """
    print("在线搜索: 重新扫描目录...", file=sys.stderr)

    scan_result = scan_folder(url, options)
    if not scan_result.get('success'):
        return {
            'query': keyword,
            'online': True,
            'total': 0,
            'results': [],
            'errors': scan_result.get('errors', ['扫描失败'])
        }

    print("在更新后的缓存中搜索...", file=sys.stderr)
    return search_local(keyword, options)


def fetch_content(docs: list, url: str, options: dict) -> dict:
    """
    抓取文档内容

    Args:
        docs: 文档列表
        url: 飞书URL
        options: 选项 (show_browser, login_timeout, limit)

    Returns:
        抓取结果
    """
    from feishu_navigator import FeishuNavigator
    from content_fetcher import fetch_document_content, save_as_markdown

    parsed = parse_feishu_url(url)
    domain = parsed['domain']

    result = {
        'success': False,
        'session_id': generate_session_id(),
        'fetched': [],
        'output_dir': CONTENT_DIR,
        'errors': []
    }

    # 过滤不支持的文件类型
    filtered_docs = [d for d in docs if os.path.splitext(d.get('name', '').lower())[1] not in SKIP_FETCH_EXTENSIONS]

    if not filtered_docs:
        result['errors'].append('没有可抓取的文档')
        return result

    navigator = None
    try:
        navigator = FeishuNavigator(domain, headless=not options.get('show_browser', False))

        if not navigator.open_and_wait_login(target_url=url, timeout=options.get('login_timeout', LOGIN_WAIT_TIMEOUT)):
            result['errors'].append('登录失败或超时')
            return result

        page = navigator.get_page()
        os.makedirs(CONTENT_DIR, exist_ok=True)

        # 构建基础URL
        base_url = domain if domain.startswith('https://') else f"https://{domain}"

        for i, doc in enumerate(filtered_docs[:options.get('limit', DEFAULT_RESULT_LIMIT)]):
            doc_url = doc.get('url')
            if not doc_url:
                continue

            if doc_url.startswith('/'):
                doc_url = base_url + doc_url

            print(f"\n[{i+1}/{len(filtered_docs)}] 抓取: {doc.get('name', 'N/A')[:30]}...", file=sys.stderr)

            if i > 0:
                time.sleep(1)

            fetch_result = fetch_document_content(page, doc_url)

            if fetch_result.get('success'):
                folder_path = doc.get('folder_path', '')
                doc_id = doc.get('id', '')
                filepath = save_as_markdown(fetch_result, CONTENT_DIR, folder_path, doc_id)
                result['fetched'].append({
                    'name': doc.get('name'),
                    'title': fetch_result.get('title'),
                    'url': doc_url,
                    'folder_path': folder_path,
                    'success': True,
                    'file': filepath,
                })
            else:
                result['fetched'].append({
                    'name': doc.get('name'),
                    'url': doc_url,
                    'success': False,
                    'error': fetch_result.get('error'),
                })

        result['success'] = True
        success_count = sum(1 for f in result['fetched'] if f.get('success'))
        print(f"\n抓取完成: {success_count}/{len(result['fetched'])}", file=sys.stderr)
        print(f"保存目录: {CONTENT_DIR}", file=sys.stderr)

    except Exception as e:
        result['errors'].append(str(e))
        print(f"抓取错误: {e}", file=sys.stderr)
    finally:
        if navigator:
            navigator.close()

    return result


def debug_page_structure(url: str, options: dict) -> dict:
    """
    调试页面结构

    Args:
        url: 飞书URL
        options: 选项

    Returns:
        调试结果
    """
    from feishu_navigator import FeishuNavigator
    from directory_scanner import DirectoryScanner

    parsed = parse_feishu_url(url)
    domain = parsed['domain']

    print(f"调试模式: {url}", file=sys.stderr)
    print(f"域名: {domain}", file=sys.stderr)

    result = {
        'success': False,
        'url': url,
        'domain': domain,
        'debug_info': '',
        'errors': []
    }

    navigator = None
    try:
        navigator = FeishuNavigator(domain, headless=not options.get('show_browser', False))

        if not navigator.open_and_wait_login(target_url=url, timeout=options.get('login_timeout', LOGIN_WAIT_TIMEOUT)):
            result['errors'].append('登录失败或超时')
            return result

        time.sleep(2)
        scanner = DirectoryScanner(navigator)
        debug_info = scanner.debug_page_structure()

        result['success'] = True
        result['debug_info'] = debug_info

    except Exception as e:
        result['errors'].append(str(e))
        print(f"调试错误: {e}", file=sys.stderr)
    finally:
        if navigator:
            navigator.close()

    return result