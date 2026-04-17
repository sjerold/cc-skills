#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书卡片构建器

飞书卡片JSON结构参考: https://open.feishu.cn/document/feishu-cards/card-json-v2-configure
"""

from typing import List, Optional, Dict


class CardBuilder:
    """飞书卡片构建器"""

    def __init__(self):
        self.card = {
            "config": {"wide_screen_mode": True},
            "elements": []
        }
        self._header = None

    def add_header(self, title: str, template: str = "blue") -> "CardBuilder":
        """
        添加标题栏

        Args:
            title: 标题文本
            template: 颜色模板 (blue, wathet, turquoise, green, yellow,
                       orange, red, carmine, violet, purple, indigo, grey)

        Returns:
            self (链式调用)
        """
        self._header = {
            "title": {"tag": "plain_text", "content": title},
            "template": template
        }
        return self

    def add_div(self, text: str, text_type: str = "lark_md") -> "CardBuilder":
        """
        添加文本段落

        Args:
            text: 文本内容
            text_type: 文本类型 (plain_text, lark_md)

        Returns:
            self (链式调用)
        """
        self.card["elements"].append({
            "tag": "div",
            "text": {"tag": text_type, "content": text}
        })
        return self

    def add_fields(self, fields: List[dict]) -> "CardBuilder":
        """
        添加多列字段

        Args:
            fields: 字段列表，每个字段格式:
                    {"is_short": True/False, "text": {"tag": "lark_md", "content": "内容"}}

        Returns:
            self (链式调用)
        """
        self.card["elements"].append({
            "tag": "div",
            "fields": fields
        })
        return self

    def add_action(self, actions: List[dict]) -> "CardBuilder":
        """
        添加交互按钮（仅支持跳转链接）

        Args:
            actions: 按钮列表，每个按钮格式:
                    {"tag": "button", "text": {...}, "type": "primary",
                     "click": {"type": "open_url", "value": "URL"}}

        Returns:
            self (链式调用)
        """
        self.card["elements"].append({
            "tag": "action",
            "actions": actions
        })
        return self

    def add_note(self, text: str) -> "CardBuilder":
        """
        添加备注（底部小字）

        Args:
            text: 备注文本

        Returns:
            self (链式调用)
        """
        self.card["elements"].append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": text}]
        })
        return self

    def add_hr(self) -> "CardBuilder":
        """
        添加分割线

        Returns:
            self (链式调用)
        """
        self.card["elements"].append({"tag": "hr"})
        return self

    def add_collapsible_panel(
        self,
        title: str,
        elements: List[dict],
        expanded: bool = False,
        title_tag: str = "plain_text"
    ) -> "CardBuilder":
        """
        添加折叠面板（飞书 V7.9+）

        Args:
            title: 标题（点击展开/收起）
            elements: 折叠内容元素列表，每个元素格式如:
                      {"tag": "div", "text": {"tag": "lark_md", "content": "内容"}}
            expanded: 初始展开状态（False=折叠，True=展开）
            title_tag: 标题文本类型（plain_text 或 lark_md）

        Returns:
            self (链式调用)
        """
        self.card["elements"].append({
            "tag": "collapsible_panel",
            "expanded": expanded,
            "header": {
                "title": {"tag": title_tag, "content": title}
            },
            "elements": elements
        })
        return self

    def add_collapsible_div(
        self,
        title: str,
        content: str,
        expanded: bool = False,
        content_type: str = "lark_md"
    ) -> "CardBuilder":
        """
        添加折叠文本面板（简化版，用于单个文本内容）

        Args:
            title: 标题
            content: 文本内容
            expanded: 初始展开状态
            content_type: 内容类型（lark_md 或 plain_text）

        Returns:
            self (链式调用)
        """
        return self.add_collapsible_panel(
            title=title,
            elements=[{
                "tag": "div",
                "text": {"tag": content_type, "content": content}
            }],
            expanded=expanded
        )

    def build(self) -> dict:
        """
        构建完整卡片JSON

        Returns:
            飞书卡片JSON结构
        """
        result = self.card.copy()
        if self._header:
            result["header"] = self._header
        return result

    def reset(self) -> "CardBuilder":
        """
        重置构建器

        Returns:
            self (链式调用)
        """
        self.card = {
            "config": {"wide_screen_mode": True},
            "elements": []
        }
        self._header = None
        return self


def build_button(text: str, url: str, button_type: str = "primary") -> dict:
    """
    构建跳转按钮

    Args:
        text: 按钮文本
        url: 跳转URL
        button_type: 按钮类型 (primary, default, danger)

    Returns:
        按钮元素JSON
    """
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": text},
        "type": button_type,
        "click": {"type": "open_url", "value": url}
    }


def build_field(content: str, is_short: bool = True) -> dict:
    """
    构建字段元素

    Args:
        content: 字段内容（支持lark_md格式）
        is_short: 是否为短字段（半宽）

    Returns:
        字段元素JSON
    """
    return {
        "is_short": is_short,
        "text": {"tag": "lark_md", "content": content}
    }