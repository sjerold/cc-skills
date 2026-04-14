#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书文档导出模块 - 通过 UI 操作导出文档为 Word 格式
"""
import sys
import os
import io
import time
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def export_docx_via_ui(page, doc_url: str, output_dir: str = None) -> dict:
    """
    通过 UI 操作导出飞书文档为 Word 格式

    Args:
        page: Playwright 页面对象
        doc_url: 文档 URL
        output_dir: 输出目录（默认 ~/Downloads）

    Returns:
        {
            'success': bool,
            'file_path': str,
            'file_name': str,
            'file_size': int,
            'error': str
        }
    """
    result = {
        'success': False,
        'file_path': None,
        'file_name': None,
        'file_size': 0,
        'error': None
    }

    if output_dir is None:
        output_dir = os.path.expanduser('~/Downloads')

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    try:
        print(f"  [导出] 开始导出: {doc_url[:60]}...", file=sys.stderr)

        # 导航到文档页面
        page.goto(doc_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(3)

        # 滚动确保页面加载
        page.keyboard.press('Control+Home')
        time.sleep(1)

        # 1. 打开更多菜单
        print(f"  [导出] 打开更多菜单...", file=sys.stderr)
        more_btn = page.locator('[data-e2e="suite-more-btn"]')
        if more_btn.count() > 0:
            more_btn.first.click()
        else:
            result['error'] = '无法找到更多菜单按钮'
            return result
        time.sleep(2)

        # 2. Hover "下载为" 触发子菜单（支持中英文）
        print(f"  [导出] 触发下载子菜单...", file=sys.stderr)
        download_as_item = page.locator('[role="menuitem"]:has-text("下载为"), [role="menuitem"]:has-text("Download As")')
        if download_as_item.count() > 0:
            download_as_item.first.hover()
            time.sleep(2)
        else:
            result['error'] = '无法找到下载选项'
            return result

        # 3. 点击 Word 选项
        print(f"  [导出] 选择 Word 格式...", file=sys.stderr)
        word_item = page.locator('[role="menuitem"]:has-text("Word")')
        word_found = False
        for i in range(word_item.count()):
            text = word_item.nth(i).text_content()
            if text and text.strip() == 'Word':
                word_item.nth(i).click()
                word_found = True
                break

        if not word_found:
            result['error'] = '无法找到 Word 选项'
            return result

        time.sleep(3)

        # 4. 处理导出对话框 - 选择 "仅正文" / "Content only"
        print(f"  [导出] 处理导出对话框...", file=sys.stderr)
        content_only = page.locator('text="Content only", text="仅正文"')
        if content_only.count() > 0:
            content_only.first.click()
            time.sleep(1)

        # 5. 点击 Export 按钮，使用 expect_download 捕获下载
        print(f"  [导出] 点击导出按钮...", file=sys.stderr)
        export_btn = page.locator('button:has-text("Export"), button:has-text("导出")')

        with page.expect_download(timeout=120000) as download_info:
            if export_btn.count() > 0:
                export_btn.first.click()
            else:
                result['error'] = '无法找到导出按钮'
                return result

        # 6. 获取下载文件并保存
        download = download_info.value
        file_name = download.suggested_filename
        print(f"  [导出] 下载文件: {file_name}", file=sys.stderr)

        save_path = os.path.join(output_dir, file_name)
        download.save_as(save_path)

        if os.path.exists(save_path):
            file_size = os.path.getsize(save_path)
            result['success'] = True
            result['file_path'] = save_path
            result['file_name'] = file_name
            result['file_size'] = file_size
            print(f"  [导出] 成功! 文件: {save_path} ({file_size} 字节)", file=sys.stderr)
        else:
            result['error'] = '文件保存失败'

    except Exception as e:
        result['error'] = str(e)
        print(f"  [导出] 错误: {e}", file=sys.stderr)

    return result


if __name__ == '__main__':
    import argparse
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description='飞书文档导出工具')
    parser.add_argument('url', help='文档 URL')
    parser.add_argument('-o', '--output', default=os.path.expanduser('~/Downloads'), help='输出目录')

    args = parser.parse_args()

    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp('http://127.0.0.1:9222')
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()

    result = export_docx_via_ui(page, args.url, args.output)

    print(f"\n结果:")
    print(f"  成功: {result['success']}")
    print(f"  文件: {result['file_path']}")
    print(f"  大小: {result['file_size']} 字节")
    print(f"  错误: {result['error']}")

    pw.stop()