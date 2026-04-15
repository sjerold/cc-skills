#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 抓取模块

负责飞书文档内容抓取，支持 API 和 DOM 两种方式。
"""

from .fetcher import fetch_document_content
from .api_fetcher import fetch_via_api, extract_content_from_blocks, extract_block_text
from .dom_fetcher import scroll_and_extract, extract_title, extract_tables_from_dom
from .table_parser import build_markdown_table
from .markdown_writer import save_as_markdown

__all__ = [
    'fetch_document_content',
    'fetch_via_api',
    'extract_content_from_blocks',
    'extract_block_text',
    'scroll_and_extract',
    'extract_title',
    'extract_tables_from_dom',
    'build_markdown_table',
    'save_as_markdown',
]