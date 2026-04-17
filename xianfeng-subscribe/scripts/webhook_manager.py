#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Webhook管理模块
"""

import json
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, List, Optional

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import WEBHOOKS_FILE, COMMON_PATH

sys.path.insert(0, COMMON_PATH)
try:
    from utils import log
except ImportError:
    def log(msg):
        print(msg)


def _load_config() -> dict:
    """加载配置文件"""
    if not os.path.exists(WEBHOOKS_FILE):
        return {"webhooks": [], "default_webhook_id": None}
    try:
        with open(WEBHOOKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"加载配置失败: {e}")
        return {"webhooks": [], "default_webhook_id": None}


def _save_config(config: dict) -> bool:
    """保存配置文件"""
    try:
        os.makedirs(os.path.dirname(WEBHOOKS_FILE), exist_ok=True)
        with open(WEBHOOKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"保存配置失败: {e}")
        return False


def _generate_id() -> str:
    """生成Webhook ID"""
    return f"wh_{uuid.uuid4().hex[:8]}"


def register_webhook(name: str, url: str) -> dict:
    """
    注册Webhook

    Args:
        name: Webhook名称
        url: Webhook地址

    Returns:
        注册结果
    """
    config = _load_config()

    # 检查URL是否已存在
    for wh in config.get("webhooks", []):
        if wh.get("url") == url:
            log(f"Webhook URL已存在: {wh.get('id')}")
            return {
                "success": False,
                "error": "URL已存在",
                "existing_id": wh.get("id")
            }

    # 创建新Webhook
    webhook_id = _generate_id()
    webhook = {
        "id": webhook_id,
        "name": name,
        "url": url,
        "created_at": datetime.now().isoformat(),
        "enabled": True
    }

    config["webhooks"].append(webhook)

    # 如果是第一个，设为默认
    if len(config["webhooks"]) == 1:
        config["default_webhook_id"] = webhook_id

    if _save_config(config):
        log(f"注册成功: {webhook_id} - {name}")
        return {
            "success": True,
            "webhook": webhook,
            "is_default": config["default_webhook_id"] == webhook_id
        }
    else:
        return {"success": False, "error": "保存失败"}


def list_webhooks() -> List[dict]:
    """
    列出所有Webhook

    Returns:
        Webhook列表
    """
    config = _load_config()
    webhooks = config.get("webhooks", [])
    default_id = config.get("default_webhook_id")

    result = []
    for wh in webhooks:
        wh_copy = wh.copy()
        wh_copy["is_default"] = wh.get("id") == default_id
        result.append(wh_copy)

    return result


def get_webhook(webhook_id: str) -> Optional[dict]:
    """
    获取指定Webhook

    Args:
        webhook_id: Webhook ID

    Returns:
        Webhook信息或None
    """
    config = _load_config()
    for wh in config.get("webhooks", []):
        if wh.get("id") == webhook_id:
            return wh.copy()
    return None


def get_webhook_by_name(name: str) -> Optional[dict]:
    """
    通过名称获取Webhook

    Args:
        name: Webhook名称

    Returns:
        Webhook信息或None
    """
    config = _load_config()
    for wh in config.get("webhooks", []):
        if wh.get("name") == name:
            return wh.copy()
    return None


def remove_webhook(webhook_id: str) -> dict:
    """
    删除Webhook

    Args:
        webhook_id: Webhook ID

    Returns:
        删除结果
    """
    config = _load_config()
    webhooks = config.get("webhooks", [])

    # 查找并删除
    found = False
    new_webhooks = []
    for wh in webhooks:
        if wh.get("id") == webhook_id:
            found = True
        else:
            new_webhooks.append(wh)

    if not found:
        return {"success": False, "error": "Webhook不存在"}

    config["webhooks"] = new_webhooks

    # 如果删除的是默认，更新默认
    if config.get("default_webhook_id") == webhook_id:
        if new_webhooks:
            config["default_webhook_id"] = new_webhooks[0].get("id")
        else:
            config["default_webhook_id"] = None

    if _save_config(config):
        log(f"删除成功: {webhook_id}")
        return {"success": True}
    else:
        return {"success": False, "error": "保存失败"}


def set_default_webhook(webhook_id: str) -> dict:
    """
    设置默认Webhook

    Args:
        webhook_id: Webhook ID

    Returns:
        设置结果
    """
    config = _load_config()

    # 检查是否存在
    found = False
    for wh in config.get("webhooks", []):
        if wh.get("id") == webhook_id:
            found = True
            break

    if not found:
        return {"success": False, "error": "Webhook不存在"}

    config["default_webhook_id"] = webhook_id

    if _save_config(config):
        log(f"设置默认: {webhook_id}")
        return {"success": True}
    else:
        return {"success": False, "error": "保存失败"}


def get_default_webhook() -> Optional[dict]:
    """
    获取默认Webhook

    Returns:
        默认Webhook信息或None
    """
    config = _load_config()
    default_id = config.get("default_webhook_id")

    if not default_id:
        return None

    return get_webhook(default_id)


def test_webhook(webhook_id: str) -> dict:
    """
    测试Webhook连接

    Args:
        webhook_id: Webhook ID

    Returns:
        测试结果
    """
    webhook = get_webhook(webhook_id)
    if not webhook:
        return {"success": False, "error": "Webhook不存在"}

    # 发送测试消息
    from card_sender import send_text
    return send_text(webhook.get("url"), "衔风订阅测试消息，连接成功！")