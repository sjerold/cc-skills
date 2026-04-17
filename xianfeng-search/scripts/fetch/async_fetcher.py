#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 异步并行抓取

使用 asyncio 并行抓取多个文档，同一 browser context 下创建多个 page。
"""

import sys
import os
import asyncio

# 添加路径
scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

# 添加 common 模块路径
plugins_dir = os.path.dirname(scripts_dir)
common_path = os.path.join(plugins_dir, 'common', 'scripts')
if common_path not in sys.path:
    sys.path.insert(0, common_path)

from chrome_manager import get_browser_async, get_page_async, close_browser_async, close_page_async

from core import CONTENT_WAIT_TIMEOUT, extract_doc_id, CONTENT_DIR
from fetch.api_fetcher import fetch_via_api
from fetch.dom_fetcher import scroll_and_extract, extract_title
from fetch.markdown_writer import save_as_markdown


async def fetch_single_doc_async(page, doc_url: str, doc_info: dict) -> dict:
    """
    异步抓取单个文档 - 使用 API 拦截方式

    Args:
        page: Playwright异步page对象
        doc_url: 文档URL
        doc_info: 文档信息（包含name, folder_path, id等）

    Returns:
        抓取结果字典
    """
    result = {
        'url': doc_url,
        'name': doc_info.get('name', 'N/A'),
        'success': False,
    }

    doc_id = extract_doc_id(doc_url)

    # 检测是否是表格类型
    is_sheet = '/sheets/' in doc_url.lower() or '/sheet/' in doc_url.lower()

    # 捕获的 API 响应
    captured_responses = []

    async def on_response(response):
        url = response.url
        # 拦截 docx 和 sheet 相关 API
        keywords = ['client_vars', 'block', 'vars']
        if is_sheet:
            keywords.extend(['sheet', 'grid', 'cells', 'spreadsheet', 'range'])
        if any(kw in url.lower() for kw in keywords):
            captured_responses.append(response)

    try:
        # 监听 API 响应
        page.on('response', on_response)

        # 导航到文档页面
        await page.goto(doc_url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # 滚动触发 API 调用
        for _ in range(10):
            for _ in range(5):
                await page.keyboard.press('PageDown')
                await asyncio.sleep(0.1)
            await asyncio.sleep(1)

        await page.keyboard.press('Control+Home')
        await asyncio.sleep(1)

        # 移除监听器
        page.remove_listener('response', on_response)

        # 处理 API 响应
        if captured_responses:
            merged_block_map = {}
            merged_block_sequence = []
            title = doc_info.get('name', '未命名文档')
            seen_block_ids = set()

            # Sheet 数据收集
            sheet_cells = {}
            max_row = 0
            max_col = 0

            for response in captured_responses:
                try:
                    data = await response.json()
                    if data.get('code') != 0:
                        continue

                    doc_data = data.get('data', {})
                    block_map = doc_data.get('block_map', {})
                    block_sequence = doc_data.get('block_sequence', [])

                    for block_id, block in block_map.items():
                        if block_id not in seen_block_ids:
                            merged_block_map[block_id] = block
                            seen_block_ids.add(block_id)

                    for block_id in block_sequence:
                        if block_id not in merged_block_sequence:
                            merged_block_sequence.append(block_id)

                    meta = doc_data.get('meta_map', {}).get(doc_id, {})
                    if meta.get('title'):
                        title = meta['title']

                    # 提取 Sheet 数据
                    if is_sheet:
                        from .sheets_fetcher import parse_cell_key, extract_cell_value

                        # 从 block_map 中提取表格数据
                        for block_id, block in block_map.items():
                            block_data = block.get('data', {})
                            block_type = block_data.get('type', '')

                            if block_type in ['sheet', 'table']:
                                cells = block_data.get('cells', [])
                                if cells and isinstance(cells, list):
                                    for ri, row in enumerate(cells):
                                        if isinstance(row, list):
                                            for ci, cell in enumerate(row):
                                                text = extract_cell_value(cell)
                                                if text:
                                                    sheet_cells[(ri, ci)] = text
                                                    max_row = max(max_row, ri)
                                                    max_col = max(max_col, ci)

                                # 尝试 cell_set 格式
                                cell_set = block_data.get('cell_set', {})
                                if cell_set:
                                    for cell_key, cell_val in cell_set.items():
                                        pos = parse_cell_key(cell_key)
                                        if pos:
                                            row, col = pos
                                            text = extract_cell_value(cell_val)
                                            if text:
                                                sheet_cells[(row, col)] = text
                                                max_row = max(max_row, row)
                                                max_col = max(max_col, col)

                        # 尝试直接的 sheet_data
                        sheet_data = data.get('sheet', data.get('spreadsheet', {}))
                        if sheet_data:
                            cells = sheet_data.get('cells', sheet_data.get('data', []))
                            if isinstance(cells, list):
                                for ri, row in enumerate(cells):
                                    if isinstance(row, list):
                                        for ci, cell in enumerate(row):
                                            text = str(cell) if cell else ''
                                            if text:
                                                sheet_cells[(ri, ci)] = text
                                                max_row = max(max_row, ri)
                                                max_col = max(max_col, ci)

                except:
                    continue

            # Sheet 类型处理
            if is_sheet and sheet_cells:
                from .sheets_fetcher import build_sheet_markdown
                content = build_sheet_markdown(sheet_cells, max_row, max_col)
                if content and len(content) > 50:
                    result['success'] = True
                    result['title'] = title
                    result['content'] = content
                    result['length'] = len(content)
                    result['method'] = 'sheet_api_async'
                    return result

            # 普通文档处理
            if merged_block_map:
                # 从 block_map 提取内容
                from fetch.api_fetcher import extract_content_from_blocks
                content = extract_content_from_blocks(merged_block_map, merged_block_sequence)

                if content and len(content) > 50:
                    result['success'] = True
                    result['title'] = title
                    result['content'] = content
                    result['length'] = len(content)
                    result['method'] = 'api_async'
                    return result

        # API 方式失败，用 DOM 方式备用
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        # Sheet 类型使用 DOM 方式
        if is_sheet:
            try:
                from .sheets_fetcher import extract_sheet_id
                sheet_id = extract_sheet_id(doc_url)
                dom_result = await fetch_sheet_dom_async(page, doc_url, sheet_id)
                if dom_result and dom_result.get('content'):
                    result['success'] = True
                    result['title'] = dom_result.get('title', '未命名表格')
                    result['content'] = dom_result['content']
                    result['length'] = len(result['content'])
                    result['method'] = 'sheet_dom_async'
                    return result
            except Exception as e:
                result['error'] = f'Sheet DOM抓取失败: {e}'
                return result

        # 普通文档：提取内容
        try:
            editor = await page.query_selector('[contenteditable]')
            if editor:
                content = await editor.evaluate('el => el.innerText')
            else:
                content = await page.evaluate('document.body.innerText')

            title_elem = await page.query_selector('.doc-title, .document-title, .title, h1')
            if title_elem:
                title = await title_elem.inner_text()
            else:
                page_title = await page.title()
                import re
                title = re.sub(r'\s*[-|]\s*(飞书|Lark|Feishu).*$', '', page_title).strip()

            if content and len(content.strip()) > 50:
                result['success'] = True
                result['title'] = title or '未命名文档'
                result['content'] = content.strip()
                result['length'] = len(result['content'])
                result['method'] = 'dom_async'
            else:
                result['error'] = '内容过短或未能提取'
                result['title'] = title or '未命名文档'

        except Exception as e:
            result['error'] = str(e)

    except Exception as e:
        result['error'] = str(e)

    return result


async def fetch_docs_parallel_async(docs: list, domain: str, workers: int = 2) -> list:
    """
    异步并行抓取多个文档

    Args:
        docs: 文档列表，每个包含 url, name, folder_path, id
        domain: 飞书域名
        workers: 并发数（默认2）

    Returns:
        抓取结果列表
    """
    if not docs:
        return []

    print(f"并行抓取 {len(docs)} 个文档（{workers} 并发）", file=sys.stderr)

    # 获取浏览器
    playwright, browser = await get_browser_async()
    if not browser:
        print("无法连接Chrome", file=sys.stderr)
        return [{'success': False, 'error': '无法连接Chrome', 'name': d.get('name')} for d in docs]

    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    semaphore = asyncio.Semaphore(workers)

    results = []

    async def fetch_one(doc, idx):
        """单个文档抓取"""
        async with semaphore:
            page = None
            try:
                page = await context.new_page()
                page.set_default_timeout(30000)

                doc_url = doc.get('url')
                if not doc_url:
                    return {'success': False, 'error': '缺少URL', 'name': doc.get('name')}

                # 构建完整URL
                base_url = domain if domain.startswith('https://') else f"https://{domain}"
                if doc_url.startswith('/'):
                    doc_url = base_url + doc_url

                print(f"抓取 [{idx+1}/{len(docs)}]: {doc.get('name', 'N/A')[:30]}...", file=sys.stderr)

                result = await fetch_single_doc_async(page, doc_url, doc)

                # 如果成功，保存为Markdown
                if result.get('success') and result.get('content'):
                    folder_path = doc.get('folder_path', '')
                    doc_id = doc.get('id', '')
                    # 传递 edit_time 用于保存到文件头
                    result['edit_time'] = doc.get('edit_time')
                    filepath = save_as_markdown(result, CONTENT_DIR, folder_path, doc_id)
                    result['file'] = filepath
                    print(f"  ✓ 抓取成功: {result.get('length', 0)} 字符", file=sys.stderr)
                else:
                    print(f"  ✗ 抓取失败: {result.get('error', '未知错误')}", file=sys.stderr)

                return result

            except Exception as e:
                print(f"  ✗ 抓取异常: {e}", file=sys.stderr)
                return {'success': False, 'error': str(e), 'name': doc.get('name')}
            finally:
                if page:
                    await close_page_async(page)

    # 并行执行
    tasks = [fetch_one(doc, i) for i, doc in enumerate(docs)]
    results = await asyncio.gather(*tasks)

    # 断开连接（保持Chrome运行）
    await close_browser_async(browser, playwright, keep_running=True)

    return list(results)


def fetch_docs_parallel(docs: list, domain: str, workers: int = 2) -> list:
    """
    并行抓取多个文档（同步包装）

    Args:
        docs: 文档列表
        domain: 飞书域名
        workers: 并发数

    Returns:
        抓取结果列表
    """
    # 使用新 event loop 避免与同步 Playwright 冲突
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(fetch_docs_parallel_async(docs, domain, workers))
    finally:
        loop.close()


async def fetch_sheet_dom_async(page, doc_url: str, sheet_id: str) -> dict:
    """
    异步 DOM 方式提取表格内容

    Args:
        page: Playwright 异步页面对象
        doc_url: 表格 URL
        sheet_id: 表格 ID

    Returns:
        包含 title 和 content 的字典
    """
    import re

    result = {'title': '未命名表格', 'content': ''}

    try:
        # 等待表格容器加载
        try:
            await page.wait_for_selector('.sheet-container, .grid-container, table, [class*="sheet"]', timeout=15000)
        except:
            pass

        # 提取标题
        try:
            title_elem = await page.query_selector('.sheet-title, .title, [class*="title"]')
            if title_elem:
                result['title'] = await title_elem.inner_text()
            else:
                page_title = await page.title()
                result['title'] = re.sub(r'\s*[-|]\s*(飞书|Lark|Feishu).*$', '', page_title).strip()
        except:
            pass

        # 使用 JS 提取表格数据
        sheet_data = await page.evaluate('''
            () => {
                const result = { rows: [], maxRow: 0, maxCol: 0 };

                // 尝试多种表格选择器
                const selectors = [
                    '.sheet-container table',
                    '.grid-container table',
                    'table.sheet',
                    'table.grid',
                    'table',
                    '[class*="sheet"] table',
                    '[class*="grid"] table'
                ];

                let table = null;
                for (const sel of selectors) {
                    table = document.querySelector(sel);
                    if (table) break;
                }

                if (!table) {
                    // 尝试直接提取单元格
                    const cells = document.querySelectorAll('[class*="cell"], td, [data-col], [data-row]');
                    if (cells.length > 0) {
                        const cellMap = {};
                        let maxRow = 0, maxCol = 0;
                        cells.forEach(cell => {
                            const row = parseInt(cell.getAttribute('data-row') || cell.parentElement?.getAttribute('data-row') || 0);
                            const col = parseInt(cell.getAttribute('data-col') || cell.getAttribute('data-column') || 0);
                            const text = cell.innerText?.trim() || cell.textContent?.trim() || '';
                            if (text && row >= 0 && col >= 0) {
                                cellMap[row + ',' + col] = text;
                                maxRow = Math.max(maxRow, row);
                                maxCol = Math.max(maxCol, col);
                            }
                        });

                        for (let r = 0; r <= maxRow; r++) {
                            const rowData = [];
                            for (let c = 0; c <= maxCol; c++) {
                                rowData.push(cellMap[r + ',' + c] || '');
                            }
                            if (rowData.some(v => v)) {
                                result.rows.push(rowData);
                            }
                        }
                        result.maxRow = maxRow;
                        result.maxCol = maxCol;
                        return result;
                    }
                    return result;
                }

                const rows = table.querySelectorAll('tr');
                rows.forEach((row, ri) => {
                    const cells = row.querySelectorAll('td, th');
                    const rowData = [];
                    cells.forEach((cell, ci) => {
                        const text = cell.innerText?.trim() || '';
                        rowData.push(text);
                        result.maxCol = Math.max(result.maxCol, ci);
                    });
                    if (rowData.some(v => v)) {
                        result.rows.push(rowData);
                        result.maxRow = Math.max(result.maxRow, ri);
                    }
                });

                return result;
            }
        ''')

        if sheet_data and sheet_data.get('rows'):
            from .table_parser import build_markdown_table
            rows = sheet_data['rows']
            if len(rows) > 0:
                result['content'] = build_markdown_table(rows)

        # 如果没有提取到内容，尝试滚动收集
        if not result['content']:
            all_rows = []
            seen_content = set()

            for scroll_round in range(20):
                visible_rows = await page.evaluate('''
                    () => {
                        const rows = [];
                        const trs = document.querySelectorAll('tr');
                        trs.forEach(tr => {
                            const rect = tr.getBoundingClientRect();
                            if (rect.top >= 0 && rect.top <= window.innerHeight) {
                                const cells = tr.querySelectorAll('td, th');
                                const rowData = Array.from(cells).map(c => c.innerText?.trim() || '');
                                if (rowData.some(v => v)) {
                                    rows.push(rowData);
                                }
                            }
                        });
                        return rows;
                    }
                ''')

                if visible_rows:
                    for row in visible_rows:
                        row_key = ','.join(row)
                        if row_key not in seen_content and any(v for v in row):
                            all_rows.append(row)
                            seen_content.add(row_key)

                await page.keyboard.press('PageDown')
                await asyncio.sleep(0.3)

            if all_rows:
                from .table_parser import build_markdown_table
                result['content'] = build_markdown_table(all_rows)

    except Exception as e:
        print(f"  [Sheet DOM Async] 异常: {e}", file=sys.stderr)

    return result