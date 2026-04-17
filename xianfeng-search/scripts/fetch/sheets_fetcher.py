#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 飞书表格(Sheet)抓取

飞书表格文档使用不同的API结构，需要专门的抓取处理。
"""

import sys
import time
import re
import json
from typing import Dict, List, Optional

from .table_parser import build_markdown_table


def fetch_sheets_content(page, doc_url: str, result: dict) -> dict:
    """
    抓取飞书表格内容

    Args:
        page: Playwright页面对象
        doc_url: 表格URL
        result: 结果字典（由fetcher.py传入）

    Returns:
        包含title和content的结果字典
    """
    print(f"  [Sheet] 开始抓取表格: {doc_url[:60]}...", file=sys.stderr)

    # 提取 sheet_id
    sheet_id = extract_sheet_id(doc_url)
    if not sheet_id:
        result['error'] = '无法提取表格ID'
        return result

    # 尝试 API 方式拦截表格数据
    api_result = fetch_sheet_via_api(page, doc_url, sheet_id)
    if api_result and api_result.get('content'):
        result['title'] = api_result.get('title', '未命名表格')
        result['content'] = api_result['content']
        result['success'] = True
        result['length'] = len(result['content'])
        result['method'] = 'sheet_api'
        print(f"  [Sheet] API抓取成功: {result['title']} ({len(result['content'])} 字符)", file=sys.stderr)
        return result

    # API 失败，使用 DOM 方式
    print("  [Sheet] API方式失败，使用DOM方式...", file=sys.stderr)
    dom_result = fetch_sheet_via_dom(page, doc_url, sheet_id)
    if dom_result and dom_result.get('content'):
        result['title'] = dom_result.get('title', '未命名表格')
        result['content'] = dom_result['content']
        result['success'] = True
        result['length'] = len(result['content'])
        result['method'] = 'sheet_dom'
        print(f"  [Sheet] DOM抓取成功: {result['title']} ({len(result['content'])} 字符)", file=sys.stderr)
        return result

    result['error'] = '未能提取表格内容'
    return result


def extract_sheet_id(url: str) -> str:
    """从URL提取表格ID"""
    # 支持 /sheets/ 和 /sheet/ 两种格式
    match = re.search(r'/sheets?/([^/?]+)', url)
    if match:
        return match.group(1)
    return ''


def fetch_sheet_via_api(page, doc_url: str, sheet_id: str) -> Optional[Dict]:
    """
    通过拦截 API 获取表格数据

    飞书表格的 API 结构:
    - 可能拦截到包含 cells、rows、columns 的数据
    - 或者 sheet_data、grid_data 等结构
    """
    try:
        # 创建新页面进行抓取
        context = page.context
        api_page = context.new_page()

        captured_responses = []

        def on_response(response):
            url = response.url
            # 拦截表格数据 API（排除静态资源）
            api_patterns = [
                'client_vars', 'spreadsheet', 'sheet/read', 'sheet/get',
                'cell_data', 'grid_data', 'sheet_data', 'range', 'cells'
            ]
            skip_patterns = ['static', 'resource', '.js', '.css', 'ng-static', 'complement', 'connectors', 'intellect']

            if any(p in url.lower() for p in api_patterns) and not any(s in url.lower() for s in skip_patterns):
                captured_responses.append(response)
                print(f"  [Sheet API] 捕获: {url[:80]}...", file=sys.stderr)

        api_page.on('response', on_response)

        # 导航到表格页面
        try:
            api_page.goto(doc_url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"  [Sheet API] 导航警告: {e}", file=sys.stderr)

        time.sleep(3)

        # 滚动触发数据加载
        for _ in range(10):
            for _ in range(5):
                api_page.keyboard.press('PageDown')
                time.sleep(0.1)
            time.sleep(1)

        api_page.keyboard.press('Control+Home')
        time.sleep(2)

        # 移除监听器
        api_page.remove_listener('response', on_response)

        if not captured_responses:
            print(f"  [Sheet API] 未捕获到响应", file=sys.stderr)
            api_page.close()
            return None

        print(f"  [Sheet API] 共捕获 {len(captured_responses)} 个响应", file=sys.stderr)

        # 解析响应数据
        all_cells = {}  # {(row, col): value}
        title = '未命名表格'
        max_row = 0
        max_col = 0

        for response in captured_responses:
            try:
                data = response.json()

                # 调试：打印响应结构
                print(f"  [Sheet API] 响应URL: {response.url[:60]}...", file=sys.stderr)
                print(f"  [Sheet API] 响应结构: code={data.get('code')}, keys={list(data.keys())}", file=sys.stderr)
                if data.get('data'):
                    print(f"  [Sheet API] data.keys: {list(data.get('data', {}).keys())[:10]}", file=sys.stderr)

                # 尝试不同的数据结构
                # 结构1: client_vars 方式（类似docx）
                if data.get('code') == 0:
                    doc_data = data.get('data', {})

                    # 尝试提取表格数据
                    block_map = doc_data.get('block_map', {})
                    if block_map:
                        # 查找表格块
                        for block_id, block in block_map.items():
                            block_data = block.get('data', {})
                            block_type = block_data.get('type', '')

                            if block_type == 'sheet':
                                # Sheet 类型
                                sheet_data = block_data.get('sheet_data', {})
                                cells_data = sheet_data.get('cells', {})
                                rows_data = sheet_data.get('rows', [])
                                cols_data = sheet_data.get('columns', [])

                                # 提取单元格数据
                                for cell_key, cell_value in cells_data.items():
                                    try:
                                        # 解析坐标 (可能是 "A1" 或 row,col)
                                        if isinstance(cell_key, str):
                                            row_col = parse_cell_key(cell_key)
                                            if row_col:
                                                row, col = row_col
                                                cell_text = extract_cell_value(cell_value)
                                                if cell_text:
                                                    all_cells[(row, col)] = cell_text
                                                    max_row = max(max_row, row)
                                                    max_col = max(max_col, col)
                                    except:
                                        continue

                            elif block_type == 'table':
                                # 表格类型（可能在sheet中嵌入）
                                cells = block_data.get('cells', [])
                                if cells:
                                    for ri, row in enumerate(cells):
                                        if isinstance(row, list):
                                            for ci, cell in enumerate(row):
                                                text = extract_cell_value(cell)
                                                if text:
                                                    all_cells[(ri, ci)] = text
                                                    max_row = max(max_row, ri)
                                                    max_col = max(max_col, ci)

                    # 提取标题
                    meta = doc_data.get('meta_map', {}).get(sheet_id, {})
                    if meta.get('title'):
                        title = meta['title']

                # 结构2: 直接的 sheet API 响应
                sheet_data = data.get('sheet', data.get('spreadsheet', {}))
                if sheet_data:
                    cells = sheet_data.get('cells', sheet_data.get('data', []))
                    if isinstance(cells, list):
                        for ri, row in enumerate(cells):
                            if isinstance(row, list):
                                for ci, cell in enumerate(row):
                                    text = str(cell) if cell else ''
                                    if text:
                                        all_cells[(ri, ci)] = text
                                        max_row = max(max_row, ri)
                                        max_col = max(max_col, ci)

                    if sheet_data.get('title'):
                        title = sheet_data['title']

                # 结构3: grid_data 格式
                grid_data = data.get('grid_data', data.get('grid', {}))
                if grid_data:
                    rows = grid_data.get('rows', [])
                    for ri, row in enumerate(rows):
                        values = row.get('values', row.get('cells', []))
                        for ci, val in enumerate(values):
                            text = extract_cell_value(val)
                            if text:
                                all_cells[(ri, ci)] = text
                                max_row = max(max_row, ri)
                                max_col = max(max_col, ci)

                # 结构4: sheet/client_vars 特有格式（飞书表格API）
                # data.data.sheets[].cells 或 data.data.cell_data
                if doc_data and not all_cells:
                    # 尝试 sheets 数组
                    sheets = doc_data.get('sheets', [])
                    if sheets and isinstance(sheets, list):
                        # 取第一个sheet
                        first_sheet = sheets[0] if sheets else {}
                        cells = first_sheet.get('cells', first_sheet.get('cell_data', {}))
                        if cells:
                            if isinstance(cells, dict):
                                # key 是 "A1" 格式
                                for cell_key, cell_val in cells.items():
                                    pos = parse_cell_key(cell_key)
                                    if pos:
                                        row, col = pos
                                        text = extract_cell_value(cell_val)
                                        if text:
                                            all_cells[(row, col)] = text
                                            max_row = max(max_row, row)
                                            max_col = max(max_col, col)
                            elif isinstance(cells, list):
                                for ri, row in enumerate(cells):
                                    if isinstance(row, list):
                                        for ci, cell in enumerate(row):
                                            text = extract_cell_value(cell)
                                            if text:
                                                all_cells[(ri, ci)] = text
                                                max_row = max(max_row, ri)
                                                max_col = max(max_col, ci)

                        if first_sheet.get('title'):
                            title = first_sheet['title']

                    # 尝试直接的 cell_data 或 sheet_data
                    cell_data = doc_data.get('cell_data', {})
                    if cell_data and isinstance(cell_data, dict):
                        for cell_key, cell_val in cell_data.items():
                            pos = parse_cell_key(cell_key)
                            if pos:
                                row, col = pos
                                text = extract_cell_value(cell_val)
                                if text:
                                    all_cells[(row, col)] = text
                                    max_row = max(max_row, row)
                                    max_col = max(max_col, col)

                    sheet_data_field = doc_data.get('sheet_data', {})
                    if sheet_data_field:
                        cells = sheet_data_field.get('cells', {})
                        if cells:
                            for cell_key, cell_val in cells.items():
                                pos = parse_cell_key(cell_key)
                                if pos:
                                    row, col = pos
                                    text = extract_cell_value(cell_val)
                                    if text:
                                        all_cells[(row, col)] = text
                                        max_row = max(max_row, row)
                                        max_col = max(max_col, col)

                    # 尝试 resources 格式
                    resources = doc_data.get('resources', {})
                    if resources:
                        for res_key, res_val in resources.items():
                            if 'cells' in res_val or 'cell_data' in res_val:
                                cells = res_val.get('cells', res_val.get('cell_data', {}))
                                if isinstance(cells, dict):
                                    for cell_key, cell_val in cells.items():
                                        pos = parse_cell_key(cell_key)
                                        if pos:
                                            row, col = pos
                                            text = extract_cell_value(cell_val)
                                            if text:
                                                all_cells[(row, col)] = text
                                                max_row = max(max_row, row)
                                                max_col = max(max_col, col)

            except Exception as e:
                print(f"  [Sheet API] 解析响应失败: {e}", file=sys.stderr)
                continue

        api_page.close()

        if all_cells:
            # 构建 Markdown 表格
            content = build_sheet_markdown(all_cells, max_row, max_col)
            if content:
                return {
                    'title': title,
                    'content': content,
                }

        return None

    except Exception as e:
        print(f"  [Sheet API] 异常: {e}", file=sys.stderr)
        return None


def fetch_sheet_via_dom(page, doc_url: str, sheet_id: str) -> Optional[Dict]:
    """
    通过 DOM 方式提取表格内容

    备用方案：直接从页面 DOM 提取表格数据
    """
    try:
        # 确保在正确页面
        try:
            page.goto(doc_url, timeout=30000, wait_until="domcontentloaded")
        except:
            pass

        time.sleep(3)

        # 等待表格容器加载
        try:
            page.wait_for_selector('.sheet-container, .grid-container, table, [class*="sheet"]', timeout=15000)
        except:
            print(f"  [Sheet DOM] 未找到表格容器", file=sys.stderr)

        # 提取标题
        title = '未命名表格'
        try:
            title_elem = page.query_selector('.sheet-title, .title, [class*="title"]')
            if title_elem:
                title = title_elem.inner_text().strip()
            else:
                page_title = page.title()
                title = re.sub(r'\s*[-|]\s*(飞书|Lark|Feishu).*$', '', page_title).strip()
        except:
            pass

        # 初始化结果字典
        result = {'title': title, 'content': ''}

        # 方法1: 使用 JS 提取表格数据（包括从内部状态）
        # 首先尝试从全局对象获取表格数据
        internal_data = page.evaluate('''
            () => {
                // 飞书表格可能有全局状态对象
                const globals = [
                    'window.__INITIAL_STATE__',
                    'window.sheetData',
                    'window.spreadsheetData',
                    'window.__sheet__',
                    'window.SheetApp'
                ];

                for (const g of globals) {
                    try {
                        const obj = eval(g);
                        if (obj && obj.cells) return obj;
                        if (obj && obj.data && obj.data.cells) return obj.data;
                        if (obj && obj.sheetData) return obj.sheetData;
                    } catch (e) {}
                }

                // 尝试从 window.__REDUX_STATE__ 或类似对象获取
                try {
                    const reduxState = window.__REDUX_STATE__ || window.__PRELOADED_STATE__;
                    if (reduxState) {
                        // 查找 sheet 相关数据
                        for (const key in reduxState) {
                            if (key.includes('sheet') || key.includes('spreadsheet')) {
                                const data = reduxState[key];
                                if (data && data.cells) return { cells: data.cells };
                                if (data && data.data) return data.data;
                            }
                        }
                    }
                } catch (e) {}

                return null;
            }
        ''')

        if internal_data and internal_data.get('cells'):
            from .table_parser import build_markdown_table
            cells = internal_data['cells']
            if isinstance(cells, list):
                result['content'] = build_markdown_table(cells)
                return result
            elif isinstance(cells, dict):
                rows = []
                max_row = 0
                max_col = 0
                for key, val in cells.items():
                    pos = parse_cell_key(key)
                    if pos:
                        row, col = pos
                        text = extract_cell_value(val)
                        if text:
                            rows.append((row, col, text))
                            max_row = max(max_row, row)
                            max_col = max(max_col, col)
                # 构建表格
                table_data = []
                for r in range(max_row + 1):
                    row_data = []
                    for c in range(max_col + 1):
                        found = next((t for rr, cc, t in rows if rr == r and cc == c), '')
                        row_data.append(found)
                    if any(v for v in row_data):
                        table_data.append(row_data)
                if table_data:
                    result['content'] = build_markdown_table(table_data)
                    return result

        # 方法2: 使用 JS 提取表格数据
        # 尝试提取所有可见文本（飞书表格可能用 canvas 但有辅助文本层）
        all_text = page.evaluate('''
            () => {
                // 检查是否有辅助文本层（用于屏幕阅读器）
                const ariaLabels = document.querySelectorAll('[aria-label]');
                const ariaTexts = [];
                ariaLabels.forEach(el => {
                    const label = el.getAttribute('aria-label');
                    if (label && label.trim()) {
                        ariaTexts.push(label.trim());
                    }
                });

                // 检查是否有隐藏的文本层
                const hiddenText = document.querySelectorAll('[class*="hidden"], [class*="sr-only"], [class*="accessibility"]');
                const hiddenTexts = [];
                hiddenText.forEach(el => {
                    const text = el.innerText?.trim();
                    if (text) hiddenTexts.push(text);
                });

                // 获取所有文本内容
                const bodyText = document.body.innerText;

                return {
                    ariaTexts: ariaTexts,
                    hiddenTexts: hiddenTexts,
                    bodyText: bodyText
                };
            }
        ''')

        if all_text.get('ariaTexts'):
            # aria-label 可能包含单元格内容
            aria_content = '\n'.join(all_text['ariaTexts'])
            if len(aria_content) > 50:
                result['content'] = aria_content
                return result

        if all_text.get('hiddenTexts'):
            hidden_content = '\n'.join(all_text['hiddenTexts'])
            if len(hidden_content) > 50:
                result['content'] = hidden_content
                return result

        # 方法3: 使用 JS 提取表格 DOM 结构
        sheet_data = page.evaluate('''
            () => {
                const result = {
                    rows: [],
                    maxRow: 0,
                    maxCol: 0
                };

                // 飞书表格可能使用 Canvas 或特殊组件
                // 尝试获取表格数据属性
                const gridContainer = document.querySelector('[class*="grid-container"], [class*="sheet-grid"], [class*="canvas-container"]');
                if (gridContainer) {
                    // 检查是否有 data 属性存储表格数据
                    const dataAttr = gridContainer.getAttribute('data-cells') || gridContainer.getAttribute('data-grid');
                    if (dataAttr) {
                        try {
                            const parsed = JSON.parse(dataAttr);
                            if (parsed.cells) {
                                return { rows: parsed.cells, maxRow: parsed.cells.length - 1, maxCol: parsed.cells[0]?.length - 1 || 0 };
                            }
                        } catch (e) {}
                    }
                }

                // 尝试多种表格选择器
                const selectors = [
                    '.sheet-container table',
                    '.grid-container table',
                    'table.sheet',
                    'table.grid',
                    'table',
                    '[class*="sheet"] table',
                    '[class*="grid"] table',
                    '[class*="spreadsheet"] table'
                ];

                let table = null;
                for (const sel of selectors) {
                    table = document.querySelector(sel);
                    if (table) break;
                }

                if (!table) {
                    // 尝试直接提取单元格（飞书表格可能用 div/grid）
                    const cellSelectors = [
                        '[class*="cell"]',
                        '[data-cell]',
                        '[data-row][data-col]',
                        'td',
                        'th'
                    ];
                    for (const sel of cellSelectors) {
                        const cells = document.querySelectorAll(sel);
                        if (cells.length > 0) {
                            const cellMap = {};
                            let maxRow = 0, maxCol = 0;
                            cells.forEach(cell => {
                                // 尝试多种方式获取行列信息
                                const rowAttr = cell.getAttribute('data-row') || cell.parentElement?.getAttribute('data-row') || cell.closest('[data-row]')?.getAttribute('data-row');
                                const colAttr = cell.getAttribute('data-col') || cell.getAttribute('data-column') || cell.closest('[data-col]')?.getAttribute('data-col');
                                const row = parseInt(rowAttr || 0);
                                const col = parseInt(colAttr || 0);
                                const text = cell.innerText?.trim() || cell.textContent?.trim() || '';
                                if (text && row >= 0 && col >= 0) {
                                    cellMap[row + ',' + col] = text;
                                    maxRow = Math.max(maxRow, row);
                                    maxCol = Math.max(maxCol, col);
                                }
                            });

                            if (Object.keys(cellMap).length > 0) {
                                // 构建行数据
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
                        }
                    }
                    return result;
                }

                // 从 table 元素提取
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
            rows = sheet_data['rows']
            if len(rows) > 0:
                # 构建 Markdown 表格
                content = build_markdown_table(rows)
                if content:
                    return {
                        'title': title,
                        'content': content,
                    }

        # 方法2: 滚动提取可见单元格
        print("  [Sheet DOM] 尝试滚动提取...", file=sys.stderr)
        all_rows = []
        seen_content = set()

        for scroll_round in range(20):
            visible_rows = page.evaluate('''
                () => {
                    const rows = [];
                    // 查找可见的行
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

            # 滚动到下一页
            page.keyboard.press('PageDown')
            time.sleep(0.3)

        if all_rows:
            content = build_markdown_table(all_rows)
            if content:
                return {
                    'title': title,
                    'content': content,
                }

        return None

    except Exception as e:
        print(f"  [Sheet DOM] 异常: {e}", file=sys.stderr)
        return None


def parse_cell_key(key: str) -> Optional[tuple]:
    """
    解析单元格键值，返回 (row, col)

    支持格式:
    - "A1" -> (0, 0)
    - "B2" -> (1, 1)
    - "R1C1" -> (0, 0)
    - "row_0_col_0" -> (0, 0)
    """
    if not key:
        return None

    # A1 格式
    match = re.match(r'^([A-Z]+)(\d+)$', key.upper())
    if match:
        col_str = match.group(1)
        row_num = int(match.group(2)) - 1  # A1 = row 0

        # 将字母转换为列号
        col = 0
        for i, c in enumerate(col_str):
            col += (ord(c) - ord('A') + 1) * (26 ** (len(col_str) - i - 1))
        col -= 1  # A = col 0

        return (row_num, col)

    # R1C1 格式
    match = re.match(r'^R(\d+)C(\d+)$', key.upper())
    if match:
        row = int(match.group(1)) - 1
        col = int(match.group(2)) - 1
        return (row, col)

    # row_col 格式
    match = re.match(r'row[_\-]?(\d+)[_\-]?col[_\-]?(\d+)', key.lower())
    if match:
        return (int(match.group(1)), int(match.group(2)))

    return None


def extract_cell_value(cell_data) -> str:
    """
    从单元格数据中提取文本值

    支持多种数据格式:
    - 直接字符串
    - {text: "value"} 格式
    - {value: "xxx"} 格式
    - 复杂的格式化数据
    """
    if cell_data is None:
        return ''

    if isinstance(cell_data, str):
        return cell_data.strip()

    if isinstance(cell_data, (int, float)):
        return str(cell_data)

    if isinstance(cell_data, dict):
        # 尝试多种字段
        for key in ['text', 'value', 'content', 'display_value', 'formatted_value', 'raw_value']:
            val = cell_data.get(key)
            if val:
                if isinstance(val, str):
                    return val.strip()
                elif isinstance(val, dict):
                    # 嵌套结构
                    inner_text = val.get('text', val.get('content', ''))
                    if inner_text:
                        return str(inner_text).strip()
                else:
                    return str(val).strip()

        # 复杂格式 - 可能是富文本
        text_data = cell_data.get('text_data', {})
        if text_data:
            parts = []
            for k in sorted(text_data.keys()):
                v = text_data[k]
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, dict):
                    parts.append(v.get('text', v.get('content', '')))
            return ''.join(parts).strip()

    return ''


def build_sheet_markdown(cells: dict, max_row: int, max_col: int) -> str:
    """
    构建表格的 Markdown 格式

    Args:
        cells: {(row, col): value} 格式的单元格数据
        max_row: 最大行号
        max_col: 最大列号

    Returns:
        Markdown 表格字符串
    """
    if not cells or max_row < 0 or max_col < 0:
        return ''

    # 构建行数据
    rows = []
    for r in range(max_row + 1):
        row_data = []
        for c in range(max_col + 1):
            value = cells.get((r, c), '')
            row_data.append(value)
        # 只保留有内容的行
        if any(v for v in row_data):
            rows.append(row_data)

    if not rows:
        return ''

    # 使用 table_parser 的函数构建表格
    return build_markdown_table(rows)