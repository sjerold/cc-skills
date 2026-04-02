#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风搜索 - CLI入口

工作流程:
1. 扫描: 打开浏览器 → 遍历目录 → 保存文档树JSON
2. 缓存: 扫描 → 抓取文档内容 → 保存为MD
3. 搜索: 读取本地JSON → 匹配文件名 → 返回结果(秒级)
"""

import sys
import os
import json
import io
import argparse

# 确保 UTF-8 编码 (Windows cmd默认GBK)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_RESULT_LIMIT, CACHE_DIR, CONTENT_DIR
from cache_manager import get_all_cache_status, clear_all_caches, get_all_cached_docs
from operations import (
    scan_folder,
    search_local,
    search_online,
    fetch_content,
    debug_page_structure,
)


def main():
    parser = argparse.ArgumentParser(
        description='衔风搜索 - 飞书云文档智能搜索工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
命令示例:
  扫描目录树:
    xianfeng_search.py 扫描 --url <飞书文件夹URL>

  缓存文档(扫描+抓取MD):
    xianfeng_search.py 缓存 --url <飞书文件夹URL>

  搜索本地缓存:
    xianfeng_search.py <关键词>

  显示缓存状态:
    xianfeng_search.py --status

缓存目录: ~/Downloads/衔风云文档缓存/
        '''
    )

    parser.add_argument('command', nargs='?', choices=['扫描', '缓存', '搜索'], help='命令: 扫描/缓存/搜索')
    parser.add_argument('keyword', nargs='?', help='搜索关键词')
    parser.add_argument('--url', '-u', help='飞书URL')
    parser.add_argument('--status', action='store_true', help='显示缓存状态')
    parser.add_argument('--clear', action='store_true', help='清理缓存')
    parser.add_argument('--close', action='store_true', help='关闭Chrome进程')
    parser.add_argument('--reset', action='store_true', help='重置登录session')
    parser.add_argument('-n', '--limit', type=int, default=DEFAULT_RESULT_LIMIT, help='限制结果数量')
    parser.add_argument('--show-browser', action='store_true', help='显示浏览器')
    parser.add_argument('--json', action='store_true', help='JSON输出')

    args = parser.parse_args()

    # 确保缓存目录存在
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(CONTENT_DIR, exist_ok=True)

    options = {
        'limit': args.limit,
        'show_browser': args.show_browser,
        'json': args.json,
    }

    # 显示缓存状态
    if args.status:
        status = get_all_cache_status()
        status['cache_dir'] = CACHE_DIR
        status['content_dir'] = CONTENT_DIR
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return

    # 清理缓存
    if args.clear:
        clear_all_caches()
        print(f"缓存已清理: {CACHE_DIR}", file=sys.stderr)
        return

    # 关闭Chrome
    if args.close:
        from feishu_navigator import close_chrome
        close_chrome()
        return

    # 重置登录session
    if args.reset:
        from feishu_navigator import close_chrome, TEMP_CHROME_DIR
        close_chrome()
        if os.path.exists(TEMP_CHROME_DIR):
            import shutil
            shutil.rmtree(TEMP_CHROME_DIR)
            print(f"已删除Chrome配置: {TEMP_CHROME_DIR}", file=sys.stderr)
        print("登录session已重置，下次需要重新登录", file=sys.stderr)
        return

    # 调试页面结构
    if args.command == '调试':
        if not args.url:
            print("错误: 调试需要指定 --url", file=sys.stderr)
            return
        result = debug_page_structure(args.url, options)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 扫描目录
    if args.command == '扫描':
        if not args.url:
            print("错误: 扫描需要指定 --url", file=sys.stderr)
            return
        result = scan_folder(args.url, options)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 缓存文档 (扫描 + 抓取)
    if args.command == '缓存':
        if not args.url:
            print("错误: 缓存需要指定 --url", file=sys.stderr)
            return
        _do_cache(args.url, options)
        return

    # 搜索
    if args.keyword or args.command == '搜索':
        keyword = args.keyword or (args.keyword if args.command != '搜索' else None)
        if not keyword:
            print("错误: 搜索需要提供关键词", file=sys.stderr)
            return
        _do_search(keyword, args.url, options)
        return

    # 无参数时显示帮助
    parser.print_help()


def _do_cache(url: str, options: dict):
    """执行缓存: 递归扫描 + 抓取"""
    print("=" * 60, file=sys.stderr)
    print("开始缓存文档...", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # 1. 递归扫描目录
    print("\n[步骤1] 扫描目录结构...", file=sys.stderr)
    _recursive_scan(url, options)

    # 2. 获取所有文档
    print(f"\n[步骤2] 获取文档列表...", file=sys.stderr)
    all_docs = get_all_cached_docs()

    # 过滤掉不支持的文件类型
    skip_extensions = ['.ppt', '.pptx', '.pdf', '.jpg', '.png', '.gif', '.mp4', '.mp3']
    docs_to_fetch = [
        d for d in all_docs
        if not any(d.get('name', '').lower().endswith(ext) for ext in skip_extensions)
        and '/file/' not in d.get('url', '')  # 跳过文件附件
    ]

    print(f"可抓取文档: {len(docs_to_fetch)} 个", file=sys.stderr)

    if not docs_to_fetch:
        print("没有可抓取的文档", file=sys.stderr)
        return

    # 3. 抓取文档内容
    print(f"\n[步骤3] 抓取文档内容...", file=sys.stderr)
    fetch_result = fetch_content(docs_to_fetch, url, options)

    # 输出结果
    print("\n" + "=" * 60, file=sys.stderr)
    print("缓存完成!", file=sys.stderr)
    print(f"扫描文档: {len(all_docs)} 个", file=sys.stderr)
    print(f"抓取成功: {sum(1 for f in fetch_result.get('fetched', []) if f.get('success'))} 个", file=sys.stderr)
    print(f"抓取失败: {sum(1 for f in fetch_result.get('fetched', []) if not f.get('success'))} 个", file=sys.stderr)
    print(f"保存目录: {CONTENT_DIR}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    if options.get('json'):
        result = {
            'success': True,
            'total_docs': len(all_docs),
            'fetch': fetch_result,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))


def _recursive_scan(url: str, options: dict, depth: int = 0):
    """
    递归扫描文件夹及其子文件夹

    Args:
        url: 飞书文件夹URL
        options: 选项
        depth: 当前深度（用于缩进显示）
    """
    indent = "  " * depth

    # 扫描当前文件夹
    scan_result = scan_folder(url, options)

    if not scan_result.get('success'):
        print(f"{indent}扫描失败", file=sys.stderr)
        return

    # 获取子文件夹列表
    status = get_all_cache_status()
    folder_id = scan_result.get('folder_id')

    # 从缓存中获取子文件夹
    from cache_manager import load_folder_cache
    cache_data = load_folder_cache(folder_id)

    if not cache_data:
        return

    children = cache_data.get('children', {})

    if not children:
        return

    print(f"{indent}发现 {len(children)} 个子文件夹，继续扫描...", file=sys.stderr)

    # 递归扫描子文件夹
    # 使用当前扫描URL的域名，避免硬编码
    from config import parse_feishu_url
    parsed = parse_feishu_url(url)
    domain = parsed.get('domain', '')

    for child_id, child_info in children.items():
        child_url = f"{domain}/drive/folder/{child_id}"
        _recursive_scan(child_url, options, depth + 1)


def _do_search(keyword: str, url: str, options: dict):
    """执行搜索"""
    if url:
        result = search_online(keyword, url, options)
    else:
        result = search_local(keyword, options)

    if options.get('json'):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 格式化输出
    print("\n" + "=" * 60)
    print(f"搜索结果: {keyword}")
    print(f"共找到 {result.get('total', 0)} 个匹配文档")
    print("=" * 60)

    if result.get('results'):
        for i, doc in enumerate(result['results'][:20], 1):
            score = doc.get('match_score', 0)
            print(f"\n{i}. [{score:.0%}] {doc.get('name', 'N/A')}")
            if doc.get('folder_path'):
                print(f"   路径: {doc['folder_path']}")
            if doc.get('url'):
                print(f"   链接: {doc['url'][:60]}...")

    if result.get('errors'):
        print("\n" + "-" * 60)
        print("提示:")
        for err in result['errors']:
            print(f"  - {err}")

    print("\n" + "=" * 60)
    print(f"缓存目录: {CACHE_DIR}")
    print("=" * 60)


if __name__ == '__main__':
    main()