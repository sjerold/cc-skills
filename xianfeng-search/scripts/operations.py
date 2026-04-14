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

# 添加common模块路径
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_SCRIPTS_DIR)
_PLUGINS_DIR = os.path.dirname(_PLUGIN_DIR)
COMMON_PATH = os.path.join(_PLUGINS_DIR, 'common', 'scripts')
sys.path.insert(0, COMMON_PATH)

from utils import log

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

    log(f"域名: {domain}")
    log(f"文件夹ID: {folder_id}")

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
            log(f"\n扫描完成: {len(flat_docs)} 个文档")
            log(f"缓存已保存到: {CACHE_DIR}")

    except Exception as e:
        result['errors'].append(str(e))
        log(f"扫描错误: {e}")
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
    log(f"在本地缓存中搜索: {keyword}")

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

        log(f"共有 {len(all_docs)} 个文档在缓存中")

        # 搜索匹配
        matched = _match_docs(all_docs, keyword)

        # 排序并限制数量
        matched.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        matched = matched[:options.get('limit', DEFAULT_RESULT_LIMIT)]

        result['total'] = len(matched)
        result['results'] = matched
        log(f"找到 {result['total']} 个匹配")

    except Exception as e:
        result['errors'].append(str(e))
        log(f"搜索错误: {e}")

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
    log("在线搜索: 重新扫描目录...")

    scan_result = scan_folder(url, options)
    if not scan_result.get('success'):
        return {
            'query': keyword,
            'online': True,
            'total': 0,
            'results': [],
            'errors': scan_result.get('errors', ['扫描失败'])
        }

    log("在更新后的缓存中搜索...")
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

            log(f"\n[{i+1}/{len(filtered_docs)}] 抓取: {doc.get('name', 'N/A')[:30]}...")

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
        log(f"\n抓取完成: {success_count}/{len(result['fetched'])}")
        log(f"保存目录: {CONTENT_DIR}")

    except Exception as e:
        result['errors'].append(str(e))
        log(f"抓取错误: {e}")
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

    log(f"调试模式: {url}")
    log(f"域名: {domain}")

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
        log(f"调试错误: {e}")
    finally:
        if navigator:
            navigator.close()

    return result


def cache_folder(url: str, options: dict) -> dict:
    """
    缓存文件夹或单个文档: 扫描 + 抓取文档内容

    Args:
        url: 飞书URL (文件夹或文档)
        options: 选项

    Returns:
        缓存结果
    """
    from feishu_navigator import FeishuNavigator
    from directory_scanner import DirectoryScanner
    from content_fetcher import fetch_document_content, save_as_markdown

    log("\n" + "=" * 60)
    log("【步骤1】解析URL并初始化")
    log("=" * 60)

    parsed = parse_feishu_url(url)
    domain = parsed['domain']
    url_type = parsed['type']
    doc_id = parsed['id']

    log(f"  ✓ 原始URL: {url}")
    log(f"  ✓ 解析域名: {domain}")
    log(f"  ✓ 文档类型: {url_type}")

    result = {
        'success': False,
        'folder_id': 'root',
        'session_id': generate_session_id(),
        'total_docs': 0,
        'fetched': [],
        'cache_saved': False,
        'errors': []
    }

    # 判断是文档还是文件夹
    if url_type == 'docx':
        # 单个文档 URL - 直接抓取内容
        log(f"  ✓ 文档ID: {doc_id}")
        result['folder_id'] = 'single_doc'

        log("\n" + "=" * 60)
        log("【步骤2】连接Chrome浏览器")
        log("=" * 60)
        log(f"  → 正在连接Chrome CDP端口...")

        navigator = None
        try:
            navigator = FeishuNavigator(domain, headless=not options.get('show_browser', False))

            log(f"  → 正在导航到目标URL...")
            if not navigator.open_and_wait_login(target_url=url, timeout=options.get('login_timeout', LOGIN_WAIT_TIMEOUT)):
                log(f"  ✗ 登录失败或超时")
                result['errors'].append('登录失败或超时')
                return result

            log(f"  ✓ Chrome连接成功")
            log(f"  ✓ 当前页面URL: {navigator.page.url}")

            time.sleep(2)
            page = navigator.get_page()

            log("\n" + "=" * 60)
            log("【步骤3】抓取文档内容")
            log("=" * 60)

            os.makedirs(CONTENT_DIR, exist_ok=True)

            doc_url = url
            log(f"\n  [1/1] {doc_id[:20]}...")
            log(f"    URL: {doc_url[:60]}...")

            fetch_result = fetch_document_content(page, doc_url)

            if fetch_result and fetch_result.get('success'):
                # 保存为Markdown
                save_name = fetch_result.get('title', doc_id[:20])
                save_path = os.path.join(CONTENT_DIR, f"{save_name}-{doc_id[:8]}.md")
                save_as_markdown(fetch_result, save_path)

                result['fetched'].append({
                    'name': save_name,
                    'url': doc_url,
                    'success': True,
                    'path': save_path,
                })
                result['total_docs'] = 1
                log(f"    ✓ 抓取成功: {save_name[:30]}")
            else:
                result['fetched'].append({
                    'name': doc_id[:20],
                    'url': doc_url,
                    'success': False,
                    'error': fetch_result.get('error', '抓取失败'),
                })
                log(f"    ✗ 抓取失败: {fetch_result.get('error', '未知错误')}")

            result['success'] = True

            log("\n" + "=" * 60)
            log("【步骤4】任务完成")
            log("=" * 60)
            log(f"  ✓ 抓取文档: 1 个")
            success_count = sum(1 for f in result['fetched'] if f.get('success'))
            log(f"  ✓ 抓取成功: {success_count} 个")
            if success_count == 0:
                log(f"  ✗ 抓取失败: 1 个")
            log(f"  ✓ 保存目录: {CONTENT_DIR}")

        except Exception as e:
            result['errors'].append(str(e))
            log(f"\n✗ 缓存错误: {e}")
        finally:
            if navigator:
                log(f"\n→ 断开Chrome连接...")
                navigator.close()

        return result

    # 文件夹 URL - 执行文件夹扫描
    folder_id = doc_id
    log(f"  ✓ 文件夹ID: {folder_id}")

    # 从父目录缓存中查找文件夹名称和路径
    folder_info = find_folder_info_from_parent_cache(folder_id)
    folder_name = folder_info.get('folder_name', '')
    folder_path = folder_info.get('folder_path', '')

    if folder_name:
        log(f"  ✓ 文件夹名称: {folder_name}")
    if folder_path:
        log(f"  ✓ 文件夹路径: {folder_path}")

    result = {
        'success': False,
        'folder_id': folder_id,
        'session_id': generate_session_id(),
        'total_docs': 0,
        'fetched': [],
        'cache_saved': False,
        'errors': []
    }

    log("\n" + "=" * 60)
    log("【步骤2】连接Chrome浏览器")
    log("=" * 60)
    log(f"  → 正在连接Chrome CDP端口...")

    navigator = None
    try:
        navigator = FeishuNavigator(domain, headless=not options.get('show_browser', False))

        log(f"  → 正在导航到目标URL...")
        if not navigator.open_and_wait_login(target_url=url, timeout=options.get('login_timeout', LOGIN_WAIT_TIMEOUT)):
            log(f"  ✗ 登录失败或超时")
            result['errors'].append('登录失败或超时')
            return result

        log(f"  ✓ Chrome连接成功")
        log(f"  ✓ 当前页面URL: {navigator.page.url}")

        time.sleep(2)
        page = navigator.get_page()

        log("\n" + "=" * 60)
        log("【步骤3】扫描文件夹目录")
        log("=" * 60)
        log(f"  → 开始扫描文件夹内容...")

        # 扫描目录
        scanner = DirectoryScanner(navigator)
        cache_data = scanner.scan_current_folder(folder_id=folder_id)

        if not cache_data:
            log(f"  ✗ 扫描失败")
            result['errors'].append('扫描失败')
            return result

        # 使用从父缓存找到的名称和路径（如果有）
        if folder_name:
            cache_data['folder_name'] = folder_name
        if folder_path:
            cache_data['folder_path'] = folder_path

        # 保存目录缓存
        save_folder_cache(folder_id, cache_data)
        flat_docs = flatten_cache(cache_data)
        result['total_docs'] = len(flat_docs)
        result['cache_saved'] = True

        log(f"  ✓ 扫描完成，发现 {len(flat_docs)} 个文档")

        # 统计文档类型
        doc_types = {}
        for doc in flat_docs:
            doc_type = doc.get('type', 'unknown')
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        for t, count in doc_types.items():
            log(f"    - {t}: {count} 个")

        # 过滤不支持的文件类型
        filtered_docs = [d for d in flat_docs if os.path.splitext(d.get('name', '').lower())[1] not in SKIP_FETCH_EXTENSIONS]
        skipped_count = len(flat_docs) - len(filtered_docs)

        if skipped_count > 0:
            log(f"  ✓ 跳过 {skipped_count} 个不支持类型的文件")

        if not filtered_docs:
            log(f"  ✓ 没有可抓取的文档，任务完成")
            result['success'] = True
            return result

        log("\n" + "=" * 60)
        log(f"【步骤4】抓取文档内容（共 {len(filtered_docs)} 个）")
        log("=" * 60)

        # 抓取文档内容
        os.makedirs(CONTENT_DIR, exist_ok=True)
        base_url = domain if domain.startswith('https://') else f"https://{domain}"

        success_count = 0
        fail_count = 0

        for i, doc in enumerate(filtered_docs[:options.get('limit', DEFAULT_RESULT_LIMIT)]):
            doc_url = doc.get('url')
            if not doc_url:
                continue

            if doc_url.startswith('/'):
                doc_url = base_url + doc_url

            doc_name = doc.get('name', 'N/A')
            log(f"\n  [{i+1}/{len(filtered_docs)}] {doc_name[:50]}...")
            log(f"    URL: {doc_url[:60]}...")

            if i > 0:
                time.sleep(1)

            fetch_result = fetch_document_content(page, doc_url)

            if fetch_result.get('success'):
                doc_folder_path = doc.get('folder_path', '')
                doc_id = doc.get('id', '')
                filepath = save_as_markdown(fetch_result, CONTENT_DIR, doc_folder_path, doc_id)
                result['fetched'].append({
                    'name': doc.get('name'),
                    'title': fetch_result.get('title'),
                    'url': doc_url,
                    'folder_path': doc_folder_path,
                    'success': True,
                    'file': filepath,
                    'length': fetch_result.get('length', 0),
                })
                success_count += 1
                log(f"    ✓ 抓取成功: {fetch_result.get('length', 0)} 字符")
            else:
                fail_count += 1
                result['fetched'].append({
                    'name': doc.get('name'),
                    'url': doc_url,
                    'success': False,
                    'error': fetch_result.get('error'),
                })
                log(f"    ✗ 抓取失败: {fetch_result.get('error', '未知错误')}")

        result['success'] = True

        log("\n" + "=" * 60)
        log("【步骤5】任务完成")
        log("=" * 60)
        log(f"  ✓ 扫描文档: {result['total_docs']} 个")
        log(f"  ✓ 抓取成功: {success_count} 个")
        if fail_count > 0:
            log(f"  ✗ 抓取失败: {fail_count} 个")
        log(f"  ✓ 保存目录: {CONTENT_DIR}")

    except Exception as e:
        result['errors'].append(str(e))
        log(f"\n✗ 缓存错误: {e}")
    finally:
        if navigator:
            log(f"\n→ 断开Chrome连接...")
            navigator.close()

    return result


# ============ 同步包装函数 (供CLI调用) ============

def scan_folder_sync(url: str, options: dict) -> dict:
    """扫描文件夹 (同步包装)"""
    return scan_folder(url, options)


def search_local_sync(keyword: str, options: dict) -> dict:
    """本地搜索 (同步包装)"""
    return search_local(keyword, options)


def search_online_sync(keyword: str, url: str, options: dict) -> dict:
    """在线搜索 (同步包装)"""
    return search_online(keyword, url, options)


def debug_page_structure_sync(url: str, options: dict) -> dict:
    """调试页面结构 (同步包装)"""
    return debug_page_structure(url, options)


def cache_folder_sync(url: str, options: dict) -> dict:
    """缓存文件夹 (同步包装)"""
    return cache_folder(url, options)


def export_docx(docs: list, url: str, options: dict) -> dict:
    """
    导出文档为 Word 格式

    Args:
        docs: 文档列表 (取第一个文档)
        url: 飞书URL
        options: 选项 (show_browser, output_dir)

    Returns:
        导出结果
    """
    from feishu_navigator import FeishuNavigator
    from docx_exporter import export_docx_via_ui

    parsed = parse_feishu_url(url)
    domain = parsed['domain']

    result = {
        'success': False,
        'session_id': generate_session_id(),
        'exported': [],
        'errors': []
    }

    if not docs:
        result['errors'].append('没有要导出的文档')
        return result

    # 只导出第一个文档
    doc = docs[0]
    doc_url = doc.get('url')
    doc_name = doc.get('name', '未知文档')

    if not doc_url:
        result['errors'].append('文档缺少 URL')
        return result

    # 构建完整 URL
    base_url = domain if domain.startswith('https://') else f"https://{domain}"
    if doc_url.startswith('/'):
        doc_url = base_url + doc_url

    log(f"\n导出文档: {doc_name}")
    log(f"URL: {doc_url}")

    output_dir = options.get('output_dir') or os.path.expanduser('~/Downloads')

    navigator = None
    try:
        navigator = FeishuNavigator(domain, headless=not options.get('show_browser', False))

        if not navigator.open_and_wait_login(timeout=options.get('login_timeout', LOGIN_WAIT_TIMEOUT)):
            result['errors'].append('登录失败或超时')
            return result

        page = navigator.get_page()

        export_result = export_docx_via_ui(page, doc_url, output_dir)

        if export_result.get('success'):
            result['success'] = True
            result['exported'].append({
                'name': doc_name,
                'url': doc_url,
                'file_path': export_result.get('file_path'),
                'file_name': export_result.get('file_name'),
                'file_size': export_result.get('file_size'),
            })
            log(f"\n导出成功: {export_result.get('file_path')}")
            log(f"文件大小: {export_result.get('file_size')} 字节")
        else:
            error = export_result.get('error', '导出失败')
            result['errors'].append(f'{doc_name}: {error}')

            # 检查是否是权限问题
            if '权限' in error or 'permission' in error.lower():
                result['errors'].append('提示: 该文档可能没有下载权限')

    except Exception as e:
        result['errors'].append(str(e))
        log(f"导出错误: {e}")
    finally:
        if navigator:
            navigator.close()

    return result


def export_docx_sync(docs: list, url: str, options: dict) -> dict:
    """导出文档 (同步包装)"""
    return export_docx(docs, url, options)