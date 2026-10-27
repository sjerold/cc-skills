#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WPS 云文档读写 CLI。

示例：
    python wps_doc.py read  https://www.kdocs.cn/l/xxxx
    python wps_doc.py info  https://www.kdocs.cn/l/xxxx
    python wps_doc.py append https://www.kdocs.cn/l/xxxx "补充说明"
    python wps_doc.py replace https://www.kdocs.cn/l/xxxx "旧文字" "新文字"
    python wps_doc.py login  https://www.kdocs.cn/l/xxxx
"""

import argparse
import asyncio
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from wps_jsapi import WpsSession, WpsError, ensure_editable, save_backup


def default_profile_dir():
    base = os.environ.get("WPS_DOCS_PROFILE")
    if base:
        return base
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(root, "wps-docs", "profile")


def emit(payload, as_json=True, text=None):
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif text is not None:
        print(text)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def session_kwargs(args, default_headless):
    if getattr(args, "use_common", False):
        return {"profile_dir": None, "headless": getattr(args, "headless", default_headless)}
    return {
        "profile_dir": args.profile_dir or default_profile_dir(),
        "headless": getattr(args, "headless", default_headless),
    }


async def cmd_info(args):
    async with WpsSession(**session_kwargs(args, True)) as s:
        await s.open(args.url)
        info = await s.info()
        if not info.get("title"):
            info["title"] = await s.page.title()
        emit({"ok": not info.get("error"), "action": "info", "url": args.url, **info})
        return 0 if not info.get("error") else 1


async def cmd_read(args):
    async with WpsSession(**session_kwargs(args, True)) as s:
        await s.open(args.url)
        info = await s.info()
        if not info.get("title"):
            info["title"] = await s.page.title()
        if info.get("error") or not info.get("textLen"):
            emit({"ok": False, "action": "read", "url": args.url, **info})
            return 1
        text = await s.text()
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
        payload = {
            "ok": True,
            "action": "read",
            "url": args.url,
            "title": info.get("title"),
            "text_len": len(text),
            "signed_out": info.get("signedOut"),
            "can_edit": info.get("canEdit"),
            "out": args.out,
        }
        if args.json:
            payload["text"] = text
            emit(payload, True)
        else:
            emit(payload, True)
            print("\n--- TEXT ---")
            print(text)
        return 0


async def cmd_append(args):
    async with WpsSession(**session_kwargs(args, False)) as s:
        await s.open(args.url)
        info = await s.info()
        ensure_editable(info)
        before = await s.text()
        backup = save_backup(args.url, before)
        result = await s.append(args.text)
        ok = bool(result.get("method")) and not result.get("error") and not result.get("saveError")
        emit({
            "ok": ok,
            "action": "append",
            "url": args.url,
            "backup": backup,
            "before_len": len(before),
            **result,
        })
        return 0 if ok else 1


async def cmd_replace(args):
    async with WpsSession(**session_kwargs(args, False)) as s:
        await s.open(args.url)
        info = await s.info()
        ensure_editable(info)
        before = await s.text()
        if args.old not in before:
            emit({"ok": False, "action": "replace", "url": args.url, "error": "not_found"})
            return 1
        backup = save_backup(args.url, before)
        result = await s.replace(args.old, args.new, replace_all=args.all)
        ok = not result.get("error") and not result.get("saveError")
        emit({
            "ok": ok,
            "action": "replace",
            "url": args.url,
            "backup": backup,
            "before_len": len(before),
            **result,
        })
        return 0 if ok else 1


async def cmd_login(args):
    profile = args.profile_dir or default_profile_dir()
    async with WpsSession(profile_dir=profile, headless=False, timeout=args.timeout) as s:
        await s.open(args.url, wait_ready=False)
        print(json.dumps({
            "ok": True,
            "action": "login",
            "message": "窗口已打开，请在 Chrome 中扫码登录 WPS，窗口不会自动关闭",
            "profile": profile,
        }, ensure_ascii=False), flush=True)
        deadline = asyncio.get_event_loop().time() + args.timeout
        while asyncio.get_event_loop().time() < deadline:
            info = await s.info()
            if not info.get("signedOut") and not info.get("error") and info.get("textLen"):
                print(json.dumps({
                    "ok": True,
                    "action": "login",
                    "login": True,
                    "profile": profile,
                    "info": info,
                }, ensure_ascii=False, indent=2), flush=True)
                return 0
            await asyncio.sleep(3)
        print(json.dumps({
            "ok": False,
            "action": "login",
            "error": "login_timeout",
            "profile": profile,
        }, ensure_ascii=False), flush=True)
        return 1


def build_parser():
    p = argparse.ArgumentParser(description="WPS 云文档读写（网页版 JSAPI）")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("url", help="kdocs/金山文档分享链接或文档 URL")
        sp.add_argument("--profile-dir", help="独立 Chrome profile 目录（默认 %%LOCALAPPDATA%%\\wps-docs\\profile）")
        sp.add_argument("--use-common", action="store_true", help="复用 common 的统一调试 Chrome（9222）")
        sp.add_argument("--headless", action="store_true", help="无头模式（读取默认开启，写入默认关闭）")
        sp.add_argument("--timeout", type=int, default=60, help="页面加载超时秒数（默认 60）")

    sp = sub.add_parser("info", help="查看文档标题、字数、登录/权限状态")
    common(sp)
    sp.set_defaults(func=cmd_info)

    sp = sub.add_parser("read", help="读取正文")
    common(sp)
    sp.add_argument("--json", action="store_true", help="输出完整 JSON（包含 text）")
    sp.add_argument("--out", help="把正文保存到文件")
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser("append", help="在文末追加一段文字")
    common(sp)
    sp.add_argument("text", help="要追加的文字")
    sp.set_defaults(func=cmd_append)

    sp = sub.add_parser("replace", help="查找并替换文字")
    common(sp)
    sp.add_argument("old", help="要替换的原文")
    sp.add_argument("new", help="替换后的文字")
    sp.add_argument(
        "--all",
        action="store_true",
        help="匹配到多处时全部替换（默认拒绝，只允许唯一匹配）",
    )
    sp.set_defaults(func=cmd_replace)

    sp = sub.add_parser("login", help="打开窗口扫码登录 WPS（保持 profile）")
    sp.add_argument("url", help="用来登录的文档 URL")
    sp.add_argument("--profile-dir", help="独立 Chrome profile 目录")
    sp.add_argument("--timeout", type=int, default=600, help="等待登录秒数（默认 600）")
    sp.set_defaults(func=cmd_login, use_common=False)

    return p


async def run(args):
    return await args.func(args)


def main():
    args = build_parser().parse_args()
    try:
        code = asyncio.run(run(args))
    except WpsError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        code = 2
    except KeyboardInterrupt:
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
