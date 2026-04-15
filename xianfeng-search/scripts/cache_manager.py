#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存管理模块 v2 - 支持增量缓存和路径复用

缓存策略:
1. 每个文件夹独立缓存，以folder_id为唯一标识
2. 记录完整路径和父子关系
3. 支持增量更新：只扫描变化的部分
4. 支持路径复用：如果父目录已缓存，可直接使用
"""

import os
import sys
import json
import time
import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    CACHE_DIR,
    JSON_CACHE_DIR,
    CACHE_MAX_AGE_HOURS,
    get_folder_cache_id,
    get_cache_path_for_folder,
)


def ensure_cache_dir():
    """确保缓存目录存在"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(JSON_CACHE_DIR, exist_ok=True)


def get_folder_cache_path(folder_id: str, folder_name: str = '') -> str:
    """
    获取文件夹缓存文件路径

    Args:
        folder_id: 文件夹ID
        folder_name: 文件夹名称（可选，用于更易识别的文件名）

    Returns:
        缓存文件完整路径
    """
    ensure_cache_dir()

    # 文件名格式：名称-ID.json（更易识别）
    if folder_name:
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', folder_name)[:40]
        filename = f"{safe_name}-{folder_id[:8]}.json"
    else:
        # 尝试查找已有缓存（通过ID匹配）
        existing = find_cache_by_folder_id(folder_id)
        if existing:
            return existing
        filename = f"{folder_id}.json"

    return os.path.join(JSON_CACHE_DIR, filename)


def find_cache_by_folder_id(folder_id: str) -> Optional[str]:
    """
    通过文件夹ID查找缓存文件路径

    Args:
        folder_id: 文件夹ID

    Returns:
        缓存文件路径，不存在返回None
    """
    if not os.path.exists(JSON_CACHE_DIR):
        return None

    # 精确匹配
    exact_path = os.path.join(JSON_CACHE_DIR, f"{folder_id}.json")
    if os.path.exists(exact_path):
        return exact_path

    # 通过ID后缀匹配（支持 名称-ID.json 格式）
    short_id = folder_id[:8]
    for filename in os.listdir(JSON_CACHE_DIR):
        if filename.endswith('.json') and filename.endswith(f"-{short_id}.json"):
            return os.path.join(JSON_CACHE_DIR, filename)

    return None


def load_folder_cache(folder_id: str) -> Optional[Dict]:
    """
    加载文件夹缓存

    Args:
        folder_id: 文件夹ID

    Returns:
        缓存数据，不存在或无效返回None
    """
    cache_path = get_folder_cache_path(folder_id)

    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载缓存失败: {e}", file=sys.stderr)
        return None


def save_folder_cache(folder_id: str, data: Dict) -> bool:
    """
    保存文件夹缓存

    Args:
        folder_id: 文件夹ID
        data: 缓存数据

    Returns:
        是否成功
    """
    # 使用 folder_name 生成易识别的文件名
    folder_name = data.get('folder_name', '')
    cache_path = get_folder_cache_path(folder_id, folder_name)

    try:
        ensure_cache_dir()

        # 添加元数据
        data['folder_id'] = folder_id
        data['cache_time'] = datetime.now().isoformat()
        data['version'] = '2.0'

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"缓存已保存: {os.path.basename(cache_path)}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"保存缓存失败: {e}", file=sys.stderr)
        return False


def is_folder_cache_valid(folder_id: str, max_age_hours: int = CACHE_MAX_AGE_HOURS, last_modified: str = None) -> bool:
    """
    检查文件夹缓存是否有效

    Args:
        folder_id: 文件夹ID
        max_age_hours: 最大有效期（小时）
        last_modified: 文件夹最后修改时间（可选，用于检测变化）

    Returns:
        是否有效
    """
    # 根目录默认无效，需要重新扫描
    if folder_id == 'root' or folder_id.startswith('root_'):
        print("根目录需要重新扫描", file=sys.stderr)
        return False

    cache_path = get_folder_cache_path(folder_id)

    if not os.path.exists(cache_path):
        return False

    try:
        file_mtime = os.path.getmtime(cache_path)
        file_age_hours = (time.time() - file_mtime) / 3600

        if file_age_hours > max_age_hours:
            print(f"缓存已过期 ({file_age_hours:.1f}小时)", file=sys.stderr)
            return False

        # 检查缓存内容
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 必须有文档列表或子文件夹
        if not data.get('docs') and not data.get('children'):
            return False

        # 比较最后修改时间
        if last_modified:
            cache_modified = data.get('last_modified')
            if cache_modified and last_modified != cache_modified:
                print(f"文件夹已更新，需要重新扫描", file=sys.stderr)
                return False

        return True
    except:
        return False


def build_folder_entry(
    folder_id: str,
    folder_name: str,
    folder_path: str,
    parent_id: str = None,
    docs: List[Dict] = None,
    children: Dict = None,
    last_modified: str = None
) -> Dict:
    """
    构建文件夹缓存条目

    Args:
        folder_id: 文件夹ID
        folder_name: 文件夹名称
        folder_path: 完整路径（从根到此）
        parent_id: 父文件夹ID
        docs: 文档列表
        children: 子文件夹缓存（递归结构）
        last_modified: 文件夹最后修改时间

    Returns:
        文件夹缓存数据
    """
    return {
        'folder_id': folder_id,
        'folder_name': folder_name,
        'folder_path': folder_path,
        'parent_id': parent_id,
        'docs': docs or [],
        'children': children or {},  # {child_folder_id: folder_entry}
        'doc_count': len(docs) if docs else 0,
        'child_count': len(children) if children else 0,
        'last_modified': last_modified,  # 文件夹最后修改时间
        'cache_time': datetime.now().isoformat(),
    }


def merge_caches(parent_cache: Dict, child_caches: Dict[str, Dict]) -> Dict:
    """
    合并多个缓存

    Args:
        parent_cache: 父文件夹缓存
        child_caches: 子文件夹缓存字典 {folder_id: cache}

    Returns:
        合并后的缓存
    """
    for child_id, child_cache in child_caches.items():
        parent_cache['children'][child_id] = {
            'folder_id': child_cache.get('folder_id'),
            'folder_name': child_cache.get('folder_name'),
            'folder_path': child_cache.get('folder_path'),
            'docs': child_cache.get('docs', []),
            'doc_count': child_cache.get('doc_count', 0),
        }

        # 递归合并子文件夹
        if child_cache.get('children'):
            parent_cache['children'][child_id]['children'] = child_cache['children']

    # 更新统计
    parent_cache['child_count'] = len(parent_cache['children'])
    parent_cache['doc_count'] = sum(
        child.get('doc_count', 0) for child in parent_cache['children'].values()
    )

    return parent_cache


def flatten_cache(cache: Dict) -> List[Dict]:
    """
    将树形缓存扁平化为文档列表

    Args:
        cache: 文件夹缓存

    Returns:
        所有文档的扁平列表
    """
    flat_list = []

    # 添加当前文件夹的文档
    for doc in cache.get('docs', []):
        doc_copy = doc.copy()
        doc_copy['folder_path'] = cache.get('folder_path', '')
        flat_list.append(doc_copy)

    # 递归添加子文件夹的文档
    for child_id, child_cache in cache.get('children', {}).items():
        flat_list.extend(flatten_cache(child_cache))

    return flat_list


def search_in_cache(cache: Dict, keyword: str, limit: int = 50) -> List[Dict]:
    """
    在缓存中搜索文档

    Args:
        cache: 文件夹缓存
        keyword: 搜索关键词
        limit: 结果数量限制

    Returns:
        匹配的文档列表
    """
    flat_list = flatten_cache(cache)

    if not flat_list:
        return []

    keyword_lower = keyword.lower()
    results = []

    for doc in flat_list:
        name = doc.get('name', '').lower()
        path = doc.get('path', '').lower() or doc.get('folder_path', '').lower()

        # 计算匹配分数
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
            matched = sum(1 for c in kw_chars if c in name)
            if matched > 0:
                score = matched / len(kw_chars) * 0.3

        if score > 0:
            doc_copy = doc.copy()
            doc_copy['match_score'] = score
            results.append(doc_copy)

    # 排序并限制数量
    results.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    return results[:limit]


def get_cache_tree_status(cache: Dict, indent: int = 0) -> str:
    """
    获取缓存树的状态字符串（用于调试）

    Args:
        cache: 缓存数据
        indent: 缩进级别

    Returns:
        格式化的状态字符串
    """
    lines = []
    prefix = "  " * indent

    folder_name = cache.get('folder_name', 'unknown')
    doc_count = cache.get('doc_count', 0)
    child_count = cache.get('child_count', 0)
    cache_time = cache.get('cache_time', 'N/A')

    lines.append(f"{prefix}├─ {folder_name}/ ({doc_count} docs, {child_count} folders) [{cache_time}]")

    for child_id, child_cache in cache.get('children', {}).items():
        lines.append(get_cache_tree_status(child_cache, indent + 1))

    return '\n'.join(lines)


def get_all_cache_status() -> Dict:
    """
    获取所有缓存的状态

    Returns:
        状态字典
    """
    status = {
        'cache_dir': CACHE_DIR,
        'json_cache_dir': JSON_CACHE_DIR,
        'caches': [],
        'total_folders': 0,
        'total_docs': 0
    }

    if not os.path.exists(JSON_CACHE_DIR):
        status['exists'] = False
        return status

    status['exists'] = True

    for filename in os.listdir(JSON_CACHE_DIR):
        if not filename.endswith('.json'):
            continue

        cache_path = os.path.join(JSON_CACHE_DIR, filename)
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            folder_id = data.get('folder_id', filename.replace('.json', ''))
            flat_docs = flatten_cache(data)

            cache_info = {
                'folder_id': folder_id,
                'folder_name': data.get('folder_name', 'unknown'),
                'folder_path': data.get('folder_path', 'unknown'),
                'doc_count': len(flat_docs),
                'child_count': data.get('child_count', 0),
                'cache_time': data.get('cache_time', 'unknown'),
                'valid': is_folder_cache_valid(folder_id)
            }

            status['caches'].append(cache_info)
            status['total_folders'] += 1
            status['total_docs'] += len(flat_docs)

        except Exception as e:
            status['caches'].append({
                'file': filename,
                'error': str(e)
            })

    return status


def get_all_cached_docs() -> List[Dict]:
    """
    获取所有缓存中的文档列表

    Returns:
        所有文档列表，包含id, name, url等信息
    """
    all_docs = []

    if not os.path.exists(JSON_CACHE_DIR):
        return all_docs

    for filename in os.listdir(JSON_CACHE_DIR):
        if not filename.endswith('.json'):
            continue

        cache_path = os.path.join(JSON_CACHE_DIR, filename)
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            flat_docs = flatten_cache(data)
            all_docs.extend(flat_docs)

        except Exception as e:
            print(f"读取缓存失败 {filename}: {e}", file=sys.stderr)
            continue

    return all_docs


def find_folder_info_from_parent_cache(folder_id: str) -> Dict:
    """
    从父目录缓存中查找文件夹信息

    当扫描子文件夹时，先从已缓存的父目录中查找该文件夹的名称和路径，
    这样可以保证路径的连续性和正确性。

    Args:
        folder_id: 当前文件夹ID

    Returns:
        {'folder_name': str, 'folder_path': str} 找不到返回空dict
    """
    if not os.path.exists(JSON_CACHE_DIR):
        return {}

    # 遍历所有缓存文件，查找哪个缓存的children包含当前folder_id
    for filename in os.listdir(JSON_CACHE_DIR):
        if not filename.endswith('.json'):
            continue

        cache_path = os.path.join(JSON_CACHE_DIR, filename)
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                parent_cache = json.load(f)

            # 在父缓存的children中查找当前文件夹
            children = parent_cache.get('children', {})
            if folder_id in children:
                child = children[folder_id]
                return {
                    'folder_name': child.get('folder_name', ''),
                    'folder_path': child.get('folder_path', ''),
                }

        except Exception as e:
            continue

    return {}


def find_parent_cache_for_child(child_folder_id: str) -> Optional[Dict]:
    """
    查找包含指定子文件夹的父缓存

    Args:
        child_folder_id: 子文件夹ID

    Returns:
        父缓存数据（包含parent_folder_id），找不到返回None
    """
    if not os.path.exists(JSON_CACHE_DIR):
        return None

    for filename in os.listdir(JSON_CACHE_DIR):
        if not filename.endswith('.json'):
            continue

        cache_path = os.path.join(JSON_CACHE_DIR, filename)
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                parent_cache = json.load(f)

            children = parent_cache.get('children', {})
            if child_folder_id in children:
                return {
                    'parent_cache': parent_cache,
                    'parent_cache_path': cache_path,
                    'parent_folder_id': parent_cache.get('folder_id'),
                }

        except Exception as e:
            continue

    return None


def update_parent_cache_child(child_folder_id: str, child_cache_data: Dict) -> bool:
    """
    更新父缓存的子文件夹数据（而非创建独立缓存）

    当单独缓存子文件夹时，如果父缓存已存在，则更新父缓存的children部分，
    避免创建重复的独立缓存文件。

    Args:
        child_folder_id: 子文件夹ID
        child_cache_data: 子文件夹扫描结果

    Returns:
        是否成功更新到父缓存
    """
    parent_info = find_parent_cache_for_child(child_folder_id)

    if not parent_info:
        return False

    parent_cache = parent_info['parent_cache']
    parent_cache_path = parent_info['parent_cache_path']

    # 更新父缓存的children部分
    parent_cache['children'][child_folder_id] = child_cache_data

    # 更新父缓存的统计信息
    # 重新计算total_doc_count（如果存在）
    if 'total_doc_count' in parent_cache:
        total = len(parent_cache.get('docs', []))
        for child_id, child in parent_cache.get('children', {}).items():
            total += child.get('total_doc_count', child.get('doc_count', 0))
        parent_cache['total_doc_count'] = total

    # 更新缓存时间
    parent_cache['cache_time'] = datetime.now().isoformat()

    # 保存更新后的父缓存
    try:
        with open(parent_cache_path, 'w', encoding='utf-8') as f:
            json.dump(parent_cache, f, ensure_ascii=False, indent=2)
        print(f"已更新父缓存: {parent_cache.get('folder_name', 'unknown')}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"更新父缓存失败: {e}", file=sys.stderr)
        return False


def save_folder_cache_smart(folder_id: str, data: Dict, force_independent: bool = False) -> bool:
    """
    智能保存文件夹缓存：
    1. 如果有父缓存包含此文件夹，更新父缓存的children（避免重复）
    2. 如果没有父缓存，创建独立缓存

    Args:
        folder_id: 文件夹ID
        data: 缓存数据
        force_independent: 强制创建独立缓存（不更新父缓存）

    Returns:
        是否成功
    """
    # 如果不强制独立，先尝试更新父缓存
    if not force_independent:
        if update_parent_cache_child(folder_id, data):
            # 成功更新父缓存，删除可能存在的独立缓存文件
            existing_cache_path = find_cache_by_folder_id(folder_id)
            if existing_cache_path:
                try:
                    os.remove(existing_cache_path)
                    print(f"已删除重复缓存: {os.path.basename(existing_cache_path)}", file=sys.stderr)
                except:
                    pass
            return True

    # 没有父缓存或强制独立，创建独立缓存
    return save_folder_cache(folder_id, data)


def clear_all_caches() -> bool:
    """清理所有缓存"""
    import shutil

    if not os.path.exists(CACHE_DIR):
        return True

    try:
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
        print("所有缓存已清理", file=sys.stderr)
        return True
    except Exception as e:
        print(f"清理缓存失败: {e}", file=sys.stderr)
        return False


def clear_folder_cache(folder_id: str) -> bool:
    """清理指定文件夹的缓存"""
    cache_path = get_folder_cache_path(folder_id)

    if not os.path.exists(cache_path):
        return True

    try:
        os.remove(cache_path)
        print(f"缓存已删除: {folder_id}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"删除缓存失败: {e}", file=sys.stderr)
        return False


# ============ 兼容旧接口 ============

def load_cache(domain: str) -> Optional[Dict]:
    """兼容旧接口：根据域名加载缓存"""
    # 尝试查找该域名下的根目录缓存
    folder_id = get_folder_cache_id(domain, 'root')
    return load_folder_cache(folder_id)


def save_cache(domain: str, data: Dict) -> bool:
    """兼容旧接口：保存缓存"""
    folder_id = data.get('folder_id') or get_folder_cache_id(domain, 'root')
    return save_folder_cache(folder_id, data)


def is_cache_valid(domain: str, max_age_hours: int = CACHE_MAX_AGE_HOURS) -> bool:
    """兼容旧接口：检查缓存有效性"""
    folder_id = get_folder_cache_id(domain, 'root')
    return is_folder_cache_valid(folder_id, max_age_hours)


def get_cache_status(domain: str = None) -> Dict:
    """兼容旧接口：获取缓存状态"""
    return get_all_cache_status()


def clear_cache(domain: str = None) -> bool:
    """兼容旧接口：清理缓存"""
    if domain:
        folder_id = get_folder_cache_id(domain, 'root')
        return clear_folder_cache(folder_id)
    return clear_all_caches()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='缓存管理模块')
    parser.add_argument('--status', action='store_true', help='显示缓存状态')
    parser.add_argument('--clear', action='store_true', help='清理所有缓存')
    parser.add_argument('--clear-folder', help='清理指定文件夹缓存')

    args = parser.parse_args()

    if args.status:
        status = get_all_cache_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
    elif args.clear:
        clear_all_caches()
    elif args.clear_folder:
        clear_folder_cache(args.clear_folder)
    else:
        parser.print_help()