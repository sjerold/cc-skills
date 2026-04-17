#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
卡片发送器
"""

import json
import os
import sys
import requests
from typing import Dict, List

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import COMMON_PATH

sys.path.insert(0, COMMON_PATH)
try:
    from utils import log
except ImportError:
    def log(msg):
        print(msg)


def send_text(webhook_url: str, text: str) -> dict:
    """
    发送纯文本消息

    Args:
        webhook_url: Webhook地址
        text: 文本内容

    Returns:
        发送结果
    """
    payload = {
        "msg_type": "text",
        "content": {"text": text}
    }
    return _send_request(webhook_url, payload)


def send_card(webhook_url: str, card_json: dict) -> dict:
    """
    发送卡片消息

    Args:
        webhook_url: Webhook地址
        card_json: 卡片JSON结构

    Returns:
        发送结果
    """
    payload = {
        "msg_type": "interactive",
        "card": card_json
    }
    return _send_request(webhook_url, payload)


def send_post(webhook_url: str, title: str, content: List[dict]) -> dict:
    """
    发送富文本消息

    Args:
        webhook_url: Webhook地址
        title: 标题
        content: 富文本内容

    Returns:
        发送结果
    """
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": content
                }
            }
        }
    }
    return _send_request(webhook_url, payload)


def _send_request(webhook_url: str, payload: dict) -> dict:
    """
    发送HTTP请求

    Args:
        webhook_url: Webhook地址
        payload: 请求体

    Returns:
        发送结果
    """
    try:
        log(f"发送消息到: {webhook_url[:50]}...")
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )

        result = response.json()

        if response.status_code == 200 and result.get("code") == 0:
            log("发送成功")
            return {"success": True, "response": result}
        else:
            error_msg = result.get("msg", "未知错误")
            log(f"发送失败: {error_msg}")
            return {"success": False, "error": error_msg, "code": result.get("code")}

    except requests.exceptions.Timeout:
        log("发送超时")
        return {"success": False, "error": "请求超时"}

    except requests.exceptions.RequestException as e:
        log(f"请求异常: {e}")
        return {"success": False, "error": str(e)}

    except json.JSONDecodeError:
        log("响应解析失败")
        return {"success": False, "error": "响应不是有效JSON"}

    except Exception as e:
        log(f"未知错误: {e}")
        return {"success": False, "error": str(e)}