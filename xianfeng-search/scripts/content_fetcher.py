#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风 - 内容抓取 (向后兼容模块)

此文件现在只是一个导入桥接，实际实现在 fetch 模块中。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 从新模块导入并重新导出
from fetch import (
    fetch_document_content,
    fetch_via_api,
    scroll_and_extract,
    build_markdown_table,
    save_as_markdown,
    extract_title,
)

from fetch.markdown_writer import save_as_markdown

__all__ = [
    'fetch_document_content',
    'fetch_via_api',
    'scroll_and_extract',
    'build_markdown_table',
    'save_as_markdown',
    'extract_title',
]