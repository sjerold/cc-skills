#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务操作模块
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import COMMON_PATH
sys.path.insert(0, COMMON_PATH)

# 尝试导入utils，如果失败则使用内置log
try:
    from utils import log
except ImportError:
    def log(msg):
        print(msg)

from webhook_manager import (
    register_webhook,
    list_webhooks,
    get_webhook,
    get_webhook_by_name,
    remove_webhook,
    set_default_webhook,
    get_default_webhook,
    test_webhook
)
from card_sender import send_text, send_card
from cards import build_notification_card, build_search_result_card


def register_webhook_op(name: str, url: str) -> dict:
    """
    注册Webhook操作

    Args:
        name: 名称
        url: Webhook地址

    Returns:
        操作结果
    """
    log(f"注册Webhook: {name}")
    result = register_webhook(name, url)

    if result.get("success"):
        log(f"注册成功: {result['webhook']['id']}")
    else:
        log(f"注册失败: {result.get('error')}")

    return result


def list_webhooks_op() -> dict:
    """
    列出Webhook操作

    Returns:
        操作结果
    """
    webhooks = list_webhooks()
    log(f"共 {len(webhooks)} 个Webhook")

    return {
        "success": True,
        "total": len(webhooks),
        "webhooks": webhooks
    }


def test_webhook_op(webhook_id: str) -> dict:
    """
    测试Webhook操作

    Args:
        webhook_id: Webhook ID

    Returns:
        操作结果
    """
    log(f"测试Webhook: {webhook_id}")
    return test_webhook(webhook_id)


def remove_webhook_op(webhook_id: str) -> dict:
    """
    删除Webhook操作

    Args:
        webhook_id: Webhook ID

    Returns:
        操作结果
    """
    log(f"删除Webhook: {webhook_id}")
    return remove_webhook(webhook_id)


def set_default_op(webhook_id: str) -> dict:
    """
    设置默认Webhook操作

    Args:
        webhook_id: Webhook ID

    Returns:
        操作结果
    """
    log(f"设置默认: {webhook_id}")
    return set_default_webhook(webhook_id)


def send_text_op(text: str, webhook_id: str = None, webhook_name: str = None) -> dict:
    """
    发送文本消息操作

    Args:
        text: 文本内容
        webhook_id: Webhook ID（可选）
        webhook_name: Webhook名称（可选）

    Returns:
        操作结果
    """
    # 获取Webhook
    webhook = None
    if webhook_id:
        webhook = get_webhook(webhook_id)
    elif webhook_name:
        webhook = get_webhook_by_name(webhook_name)
    else:
        webhook = get_default_webhook()

    if not webhook:
        return {"success": False, "error": "未找到Webhook，请先注册或指定ID"}

    log(f"发送文本到: {webhook.get('name')}")
    return send_text(webhook.get("url"), text)


def send_notification_op(
    title: str,
    content: str,
    link_url: str = None,
    webhook_id: str = None
) -> dict:
    """
    发送通知卡片操作

    Args:
        title: 标题
        content: 内容
        link_url: 链接URL
        webhook_id: Webhook ID

    Returns:
        操作结果
    """
    # 获取Webhook
    webhook = get_webhook(webhook_id) if webhook_id else get_default_webhook()

    if not webhook:
        return {"success": False, "error": "未找到Webhook"}

    log(f"发送通知卡片: {title}")
    card = build_notification_card(title, content, link_url)
    return send_card(webhook.get("url"), card)


def send_search_result_op(query: str, webhook_id: str = None) -> dict:
    """
    发送搜索结果卡片操作

    Args:
        query: 搜索关键词
        webhook_id: Webhook ID

    Returns:
        操作结果
    """
    # 获取Webhook
    webhook = get_webhook(webhook_id) if webhook_id else get_default_webhook()

    if not webhook:
        return {"success": False, "error": "未找到Webhook"}

    log(f"搜索并推送: {query}")

    # 调用衔风搜索
    try:
        # 尝试导入衔风搜索模块
        plugins_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        xianfeng_path = os.path.join(plugins_dir, "xianfeng-search", "scripts")
        sys.path.insert(0, xianfeng_path)

        from operations import search_local_sync

        search_result = search_local_sync(query, {"limit": 10})

    except ImportError:
        return {"success": False, "error": "衔风搜索模块未找到"}
    except Exception as e:
        return {"success": False, "error": f"搜索失败: {e}"}

    # 构建卡片
    card = build_search_result_card(
        query=query,
        results=search_result.get("results", []),
        total=search_result.get("total", 0)
    )

    # 发送
    return send_card(webhook.get("url"), card)