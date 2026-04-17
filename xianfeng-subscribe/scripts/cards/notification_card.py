#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知卡片模板
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from card_builder import CardBuilder, build_button


def build_notification_card(
    title: str,
    content: str,
    link_url: str = None,
    link_text: str = "查看详情",
    template: str = "blue",
    collapsible: bool = False
) -> dict:
    """
    构建通知卡片

    Args:
        title: 标题
        content: 内容
        link_url: 链接URL（可选）
        link_text: 链接按钮文本
        template: 颜色模板
        collapsible: 是否折叠内容（True=折叠，False=直接展示）

    Returns:
        飞书卡片JSON
    """
    builder = CardBuilder()

    # 标题
    builder.add_header(title, template)

    # 内容（折叠或直接展示）
    if collapsible:
        builder.add_collapsible_div(
            title="展开查看详情",
            content=content,
            expanded=False
        )
    else:
        builder.add_div(content)

    # 链接按钮（可选）
    if link_url:
        builder.add_action([build_button(link_text, link_url)])

    # 备注
    builder.add_note("由衔风订阅推送")

    return builder.build()


def build_collapsible_card(
    title: str,
    sections: list,
    template: str = "blue"
) -> dict:
    """
    构建多折叠段落卡片

    Args:
        title: 卡片标题
        sections: 段落列表，每个段落格式:
                  {"title": "段落标题", "content": "段落内容", "expanded": False}
        template: 颜色模板

    Returns:
        飞书卡片JSON
    """
    builder = CardBuilder()
    builder.add_header(title, template)

    for section in sections:
        builder.add_collapsible_div(
            title=section.get("title", ""),
            content=section.get("content", ""),
            expanded=section.get("expanded", False)
        )

    builder.add_note("由衔风订阅推送")

    return builder.build()


def build_alert_card(
    title: str,
    content: str,
    level: str = "info"
) -> dict:
    """
    构建告警卡片

    Args:
        title: 标题
        content: 内容
        level: 告警级别 (info, warning, error, success)

    Returns:
        飞书卡片JSON
    """
    # 根据级别选择颜色
    template_map = {
        "info": "blue",
        "warning": "yellow",
        "error": "red",
        "success": "green"
    }

    builder = CardBuilder()
    builder.add_header(title, template_map.get(level, "blue"))
    builder.add_div(content)
    builder.add_note("告警通知")

    return builder.build()