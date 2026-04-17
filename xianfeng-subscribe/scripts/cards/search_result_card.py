#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索结果卡片模板
"""

import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from card_builder import CardBuilder, build_button, build_field


def build_search_result_card(
    query: str,
    results: List[dict],
    total: int,
    limit: int = 10,
    folder_url: str = None
) -> dict:
    """
    构建搜索结果卡片

    Args:
        query: 搜索关键词
        results: 搜索结果列表，每个元素包含 name, url, folder_path 等
        total: 总匹配数
        limit: 显示数量限制
        folder_url: 文件夹URL（用于"查看更多"按钮）

    Returns:
        飞书卡片JSON
    """
    builder = CardBuilder()

    # 标题
    builder.add_header("衔风搜索结果", "blue")

    # 统计信息
    builder.add_fields([
        build_field(f"**关键词:** {query}"),
        build_field(f"**匹配:** {total}个")
    ])

    # 结果列表
    if results:
        # 构建文档列表（lark_md格式支持链接）
        doc_lines = []
        for i, doc in enumerate(results[:limit], 1):
            name = doc.get("name", "未知文档")
            url = doc.get("url", "")
            if url:
                # 链接格式: [文本](URL)
                doc_lines.append(f"{i}. [{name[:50]}]({url})")
            else:
                doc_lines.append(f"{i}. {name[:50]}")

        builder.add_div("\n".join(doc_lines))

        # 如果有更多结果或文件夹URL，添加按钮
        if folder_url or total > limit:
            button_url = folder_url or results[0].get("url", "")
            builder.add_action([
                build_button("查看更多", button_url, "default")
            ])

    else:
        builder.add_div("未找到匹配文档")

    # 备注
    builder.add_note("由衔风自动推送")

    return builder.build()


def build_doc_update_card(
    title: str,
    docs: List[dict],
    update_type: str = "新增"
) -> dict:
    """
    构建文档更新卡片

    Args:
        title: 标题
        docs: 文档列表
        update_type: 更新类型（新增、修改、删除）

    Returns:
        飞书卡片JSON
    """
    builder = CardBuilder()

    builder.add_header(f"文档{update_type}", "turquoise")
    builder.add_div(title)

    # 文档列表
    doc_lines = []
    for doc in docs[:10]:
        name = doc.get("name", "")
        url = doc.get("url", "")
        if url:
            doc_lines.append(f"- [{name}]({url})")
        else:
            doc_lines.append(f"- {name}")

    builder.add_div("\n".join(doc_lines))
    builder.add_note(f"共{len(docs)}个文档")

    return builder.build()