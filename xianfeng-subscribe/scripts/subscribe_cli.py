#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
衔风订阅 CLI 入口

命令格式:
    python subscribe_cli.py 注册webhook --name <名称> --url <URL>
    python subscribe_cli.py 列表webhooks
    python subscribe_cli.py 测试webhook --id <ID>
    python subscribe_cli.py 删除webhook --id <ID>
    python subscribe_cli.py 设置默认 --id <ID>
    python subscribe_cli.py 发送文本 <内容> [--webhook <ID>]
    python subscribe_cli.py 发送卡片 --title <标题> --content <内容> [--link <URL>]
    python subscribe_cli.py 发送搜索 <关键词> [--webhook <ID>]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from operations import (
    register_webhook_op,
    list_webhooks_op,
    test_webhook_op,
    remove_webhook_op,
    set_default_op,
    send_text_op,
    send_notification_op,
    send_search_result_op
)


def main():
    parser = argparse.ArgumentParser(
        description="衔风订阅 - 飞书消息推送工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 注册webhook
    reg_parser = subparsers.add_parser("注册webhook", help="注册Webhook地址")
    reg_parser.add_argument("--name", required=True, help="Webhook名称")
    reg_parser.add_argument("--url", required=True, help="Webhook地址")

    # 列表webhooks
    subparsers.add_parser("列表webhooks", help="列出所有Webhook")

    # 测试webhook
    test_parser = subparsers.add_parser("测试webhook", help="测试Webhook连接")
    test_parser.add_argument("--id", required=True, help="Webhook ID")

    # 删除webhook
    del_parser = subparsers.add_parser("删除webhook", help="删除Webhook")
    del_parser.add_argument("--id", required=True, help="Webhook ID")

    # 设置默认
    default_parser = subparsers.add_parser("设置默认", help="设置默认Webhook")
    default_parser.add_argument("--id", required=True, help="Webhook ID")

    # 发送文本
    text_parser = subparsers.add_parser("发送文本", help="发送文本消息")
    text_parser.add_argument("内容", help="文本内容")
    text_parser.add_argument("--webhook", help="Webhook ID")

    # 发送卡片
    card_parser = subparsers.add_parser("发送卡片", help="发送通知卡片")
    card_parser.add_argument("--title", required=True, help="卡片标题")
    card_parser.add_argument("--content", required=True, help="卡片内容")
    card_parser.add_argument("--link", help="链接URL")
    card_parser.add_argument("--webhook", help="Webhook ID")

    # 发送搜索
    search_parser = subparsers.add_parser("发送搜索", help="搜索并推送结果")
    search_parser.add_argument("关键词", help="搜索关键词")
    search_parser.add_argument("--webhook", help="Webhook ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行命令
    result = dispatch_command(args)

    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))


def dispatch_command(args):
    """分发命令"""
    cmd = args.command

    # 清理参数中的引号
    def clean(val):
        if val and isinstance(val, str):
            return val.strip("'\"")
        return val

    if cmd == "注册webhook":
        return register_webhook_op(clean(args.name), clean(args.url))

    elif cmd == "列表webhooks":
        return list_webhooks_op()

    elif cmd == "测试webhook":
        return test_webhook_op(args.id)

    elif cmd == "删除webhook":
        return remove_webhook_op(args.id)

    elif cmd == "设置默认":
        return set_default_op(args.id)

    elif cmd == "发送文本":
        return send_text_op(args.内容, args.webhook)

    elif cmd == "发送卡片":
        return send_notification_op(
            args.title,
            args.content,
            args.link,
            args.webhook
        )

    elif cmd == "发送搜索":
        return send_search_result_op(args.关键词, args.webhook)

    else:
        return {"success": False, "error": f"未知命令: {cmd}"}


if __name__ == "__main__":
    main()