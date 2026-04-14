#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - CLI入口

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

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)

# 添加common模块路径
_PLUGIN_DIR = os.path.dirname(_SCRIPTS_DIR)
_PLUGINS_DIR = os.path.dirname(_PLUGIN_DIR)
COMMON_PATH = os.path.join(_PLUGINS_DIR, 'common', 'scripts')
sys.path.insert(0, COMMON_PATH)

from utils import log

from config import (
    CACHE_DIR,
    JSON_CACHE_DIR,
    CONTENT_DIR,
    CLI_DESCRIPTION,
    CLI_EPILIG,
    CLI_DEFAULT_LIMIT,
    CLI_COMMANDS,
)
from cache_manager import get_all_cache_status, clear_all_caches
from operations import (
    scan_folder_sync,
    search_local_sync,
    search_online_sync,
    debug_page_structure_sync,
    cache_folder_sync,
)
from chrome_manager import kill_debug_chrome, TEMP_CHROME_DIR


def main():
    parser = argparse.ArgumentParser(
        description=CLI_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=CLI_EPILIG
    )

    parser.add_argument('command', nargs='?', choices=list(CLI_COMMANDS.values()), help='命令: 扫描/缓存/搜索/调试')
    parser.add_argument('keyword', nargs='?', help='搜索关键词')
    parser.add_argument('--url', '-u', help='飞书URL')
    parser.add_argument('--status', action='store_true', help='显示缓存状态')
    parser.add_argument('--clear', action='store_true', help='清理缓存')
    parser.add_argument('--close', action='store_true', help='关闭Chrome进程')
    parser.add_argument('--reset', action='store_true', help='重置登录session')
    parser.add_argument('-n', '--limit', type=int, default=CLI_DEFAULT_LIMIT, help='限制结果数量')
    parser.add_argument('--show-browser', action='store_true', help='显示浏览器')
    parser.add_argument('--json', action='store_true', help='JSON输出')

    args = parser.parse_args()

    # 确保缓存目录存在
    os.makedirs(JSON_CACHE_DIR, exist_ok=True)
    os.makedirs(CONTENT_DIR, exist_ok=True)

    options = {
        'limit': args.limit,
        'show_browser': args.show_browser,
        'json': args.json,
    }

    # 显示缓存状态
    if args.status:
        status = get_all_cache_status()
        status['json_dir'] = JSON_CACHE_DIR
        status['content_dir'] = CONTENT_DIR
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return

    # 清理缓存
    if args.clear:
        clear_all_caches()
        log(f"缓存已清理: {JSON_CACHE_DIR}")
        return

    # 关闭Chrome
    if args.close:
        kill_debug_chrome()
        return

    # 重置登录session
    if args.reset:
        kill_debug_chrome()
        if os.path.exists(TEMP_CHROME_DIR):
            import shutil
            shutil.rmtree(TEMP_CHROME_DIR)
            log(f"已删除Chrome配置: {TEMP_CHROME_DIR}")
        log("登录session已重置，下次需要重新登录")
        return

    # 调试页面结构
    if args.command == CLI_COMMANDS['debug']:
        if not args.url:
            log("错误: 调试需要指定 --url")
            return
        result = debug_page_structure_sync(args.url, options)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 扫描目录
    if args.command == CLI_COMMANDS['scan']:
        if not args.url:
            log("错误: 扫描需要指定 --url")
            return
        result = scan_folder_sync(args.url, options)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 缓存文档 (扫描 + 抓取)
    if args.command == CLI_COMMANDS['cache']:
        if not args.url:
            log("错误: 缓存需要指定 --url")
            return
        _do_cache(args.url, options)
        return

    # 搜索
    if args.keyword or args.command == CLI_COMMANDS['search']:
        keyword = args.keyword or (args.keyword if args.command != CLI_COMMANDS['search'] else None)
        if not keyword:
            log("错误: 搜索需要提供关键词")
            return
        _do_search(keyword, args.url, options)
        return

    # 无参数时显示帮助
    parser.print_help()


def _do_cache(url: str, options: dict):
    """执行缓存: 统一流程（一次 Chrome 会话）"""
    log("=" * 60)
    log("开始缓存文档...")
    log("=" * 60)

    # 使用统一的缓存流程
    result = cache_folder_sync(url, options)

    # 输出结果
    log("\n" + "=" * 60)
    log("缓存完成!")
    log(f"扫描文档: {result.get('total_docs', 0)} 个")
    log(f"抓取成功: {sum(1 for f in result.get('fetched', []) if f.get('success'))} 个")
    log(f"抓取失败: {sum(1 for f in result.get('fetched', []) if not f.get('success'))} 个")
    log(f"保存目录: {CONTENT_DIR}")
    log("=" * 60)

    if options.get('json'):
        print(json.dumps(result, ensure_ascii=False, indent=2))


def _do_search(keyword: str, url: str, options: dict):
    """执行搜索"""
    if url:
        result = search_online_sync(keyword, url, options)
    else:
        result = search_local_sync(keyword, options)

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
    print(f"JSON缓存: {JSON_CACHE_DIR}")
    print(f"文档内容: {CONTENT_DIR}")
    print("=" * 60)


if __name__ == '__main__':
    main()