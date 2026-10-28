#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WPS 云文档（kdocs）网页版 JSAPI 封装。

设计要点：
1. 默认复用 common 的统一调试 Chrome（端口 9222），沿用插件的会话与登录态；
2. 也可通过 profile_dir 启动独立持久化目录，适合需要单独登录 WPS 的场景；
3. 只操作 WPS 网页版暴露的 VBA 风格 JSAPI，不依赖 kdocs 私有接口；
4. 写入前由调用方备份，写入后回读校验。
"""

import asyncio
import difflib
import json
import os
import sys
import time

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COMMON_SCRIPTS = os.path.join(os.path.dirname(_PLUGIN_ROOT), "common", "scripts")
if _COMMON_SCRIPTS not in sys.path:
    sys.path.insert(0, _COMMON_SCRIPTS)

try:
    from chrome_manager import (
        get_browser_async,
        get_page_async,
        close_browser_async,
        close_page_async,
    )
    HAS_COMMON = True
    COMMON_ERR = None
except Exception as exc:  # pragma: no cover - 仅用于给出清晰提示
    HAS_COMMON = False
    COMMON_ERR = exc

from playwright.async_api import async_playwright


DOC_READY_JS = "window.WPSOpenApi && window.WPSOpenApi.documentReadyPromise"

JS_INFO = r"""async () => {
    const r = {};
    const body = document.body ? document.body.innerText : '';
    r.pageTextHead = body.slice(0, 300);
    r.signedOut = body.includes('Sign in Now') || body.includes('立即登录');
    r.canComment = body.includes('Can Comment') || body.includes('可评论');
    // 登录且没有“可评论”限制时，WPS 会显示完整编辑工具栏
    r.canEdit = !r.signedOut && !r.canComment;
    try {
        const doc = await window.WPSOpenApi.Application.ActiveDocument;
        const content = await doc.Content;
        const text = await content.Text;
        r.textLen = String(text).length;
        r.textTail = String(text).slice(-120);
        r.title = await doc.Name;
    } catch (e) {
        r.error = String(e);
    }
    return r;
}"""

JS_TEXT = r"""async () => {
    const doc = await window.WPSOpenApi.Application.ActiveDocument;
    const content = await doc.Content;
    return await content.Text;
}"""

JS_APPEND = r"""async (payload) => {
    const out = {};
    const doc = await window.WPSOpenApi.Application.ActiveDocument;
    const content = await doc.Content;
    try {
        const end = await content.End;
        const range = await doc.Range(end - 1, end - 1);
        range.Text = '\r' + payload.text;
        out.method = 'Range(End-1).Text';
    } catch (e) {
        out.error = 'append_failed: ' + String(e);
        return out;
    }
    try {
        await window.WPSOpenApi.save();
        out.saved = 'WPSOpenApi.save';
    } catch (e) {
        try {
            await doc.Save();
            out.saved = 'doc.Save';
        } catch (e2) {
            out.saveError = String(e) + ' | ' + String(e2);
        }
    }
    await new Promise(r => setTimeout(r, 2500));
    try {
        const after = await (await doc.Content).Text;
        out.afterLen = String(after).length;
        out.afterTail = String(after).slice(-120);
    } catch (e) {
        out.readError = String(e);
    }
    return out;
}"""

# 网页版没有 Content.Find；用 Range 精确改匹配片段，其余内容与格式不动。
JS_REPLACE = r"""async (payload) => {
    const out = {};
    const doc = await window.WPSOpenApi.Application.ActiveDocument;
    try {
        // 从后往前替换，避免前面的改动影响后面的索引
        for (let i = payload.spans.length - 1; i >= 0; i--) {
            const span = payload.spans[i];
            const range = await doc.Range(span[0], span[1]);
            range.Text = payload.new;
        }
        out.method = 'Range spans';
    } catch (e) {
        out.error = 'range_replace_failed: ' + String(e);
        return out;
    }
    try {
        await window.WPSOpenApi.save();
        out.saved = 'WPSOpenApi.save';
    } catch (e) {
        try {
            await doc.Save();
            out.saved = 'doc.Save';
        } catch (e2) {
            out.saveError = String(e) + ' | ' + String(e2);
        }
    }
    await new Promise(r => setTimeout(r, 2500));
    try {
        const after = await (await doc.Content).Text;
        out.afterLen = String(after).length;
        out.afterTail = String(after).slice(-120);
    } catch (e) {
        out.readError = String(e);
    }
    return out;
}"""

JS_SAVE = r"""async () => {
    const out = {};
    const doc = await window.WPSOpenApi.Application.ActiveDocument;
    try {
        await window.WPSOpenApi.save();
        out.saved = 'WPSOpenApi.save';
    } catch (e) {
        try {
            await doc.Save();
            out.saved = 'doc.Save';
        } catch (e2) {
            out.error = String(e) + ' | ' + String(e2);
        }
    }
    return out;
}"""

# 最小化改稿：一次只做一个「插入 / 删除 / 替换」原子操作。
# 修订模式下 Range 坐标会多出不可见的修订标记，因此用左侧上下文逐个试探偏移，
# 命中后再写入；写完整篇回读，必须与预期文本逐字相等。
JS_EDIT_OP = r"""async (p) => {
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const doc = await window.WPSOpenApi.Application.ActiveDocument;
    const content = await doc.Content;
    const text = String(await content.Text);
    if (text !== p.text) return {error: 'text_mismatch', actual: text.length, expected: p.text.length};
    const end = await content.End;
    const overhead = Math.max(0, end - text.length);
    const L = p.old.length;
    const W = 20;
    const ctxL = Math.min(W, p.start);
    if (ctxL === 0) return {error: 'unsupported_at_document_start'};
    const wantLeft = text.slice(p.start - ctxL, p.start);
    let start = -1;
    for (let d = 0; d <= overhead + 40; d++) {
        const cand = p.start + d;
        if (cand - ctxL < 0 || cand + L > end) continue;
        if (L > 0) {
            const s = String(await (await doc.Range(cand, cand + L)).Text);
            if (s !== p.old) continue;
        }
        const left = String(await (await doc.Range(cand - ctxL, cand)).Text);
        if (left === wantLeft) { start = cand; break; }
    }
    if (start < 0) return {error: 'no_range_match', overhead: overhead, start: p.start};
    const range = await doc.Range(start, start + L);
    range.Text = p.new;
    try {
        await window.WPSOpenApi.save();
    } catch (e) {
        return {error: 'save:' + String(e)};
    }
    await sleep(1200);
    const after = String(await (await doc.Content).Text);
    return {rangeStart: start, overhead: overhead, ok: after === p.expect, afterLen: after.length};
}"""

JS_REJECT_ALL = r"""async () => {
    const doc = await window.WPSOpenApi.Application.ActiveDocument;
    const revs = await doc.Revisions;
    const n = await revs.Count;
    if (n > 0) { await revs.RejectAll(); }
    try { await window.WPSOpenApi.save(); } catch (e) {}
    await new Promise(r => setTimeout(r, 1500));
    const after = String(await (await doc.Content).Text);
    return {rejected: n, afterLen: after.length, revs: await (await doc.Revisions).Count};
}"""


def minimal_ops(orig, pairs):
    """把每处 old→new 拆成最小编辑操作，并按文档位置倒序排列。

    倒序是关键：已写入的修订标记永远在本操作的右侧，
    这样左侧上下文才不会被「被删除但仍占坐标的文字」污染。
    """
    ops = []
    for idx, (old, new) in enumerate(pairs, 1):
        count = orig.count(old)
        if count != 1:
            raise WpsError("第 %d 处原文匹配 %d 次（须唯一）：%r" % (idx, count, old[:30]))
        base = orig.find(old)
        sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            ops.append({
                "edit": idx,
                "kind": tag,
                "start": base + i1,
                "end": base + i2,
                "old": old[i1:i2],
                "new": new[j1:j2],
            })
    ops.sort(key=lambda x: x["start"], reverse=True)
    return ops


class WpsError(RuntimeError):
    pass


def backup_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "wps-docs", "backups")
    os.makedirs(path, exist_ok=True)
    return path


def save_backup(url, text):
    name = time.strftime("%Y%m%d-%H%M%S") + ".txt"
    path = os.path.join(backup_dir(), name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# %s\n%s" % (url, text))
    return path


class WpsSession:
    """一次 WPS 文档会话。

    profile_dir 为空时复用 common 的 9222 调试 Chrome；
    指定 profile_dir 时用 Playwright 持久化目录启动独立实例。
    """

    def __init__(self, profile_dir=None, headless=True, timeout=60):
        self.profile_dir = profile_dir
        self.headless = headless
        self.timeout = timeout
        self._pw = None
        self._browser = None
        self._ctx = None
        self.page = None

    async def __aenter__(self):
        if self.profile_dir:
            os.makedirs(self.profile_dir, exist_ok=True)
            self._pw = await async_playwright().start()
            self._ctx = await self._pw.chromium.launch_persistent_context(
                self.profile_dir,
                channel="chrome",
                headless=self.headless,
                viewport=None,
                args=[
                    "--window-size=1280,900",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            self.page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        else:
            if not HAS_COMMON:
                raise WpsError(
                    "无法加载 common/scripts/chrome_manager.py，请确认插件与 common 同级安装：%r"
                    % (COMMON_ERR,)
                )
            self._pw, self._browser = await get_browser_async(headless=self.headless)
            if not self._browser:
                raise WpsError("连接调试 Chrome 失败（端口由 common 管理）")
            self.page = await get_page_async(self._browser)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
        if self._ctx:
            try:
                await self._ctx.close()
            except Exception:
                pass
            try:
                await self._pw.stop()
            except Exception:
                pass
        elif self._browser and self._pw:
            try:
                await close_browser_async(self._browser, self._pw, keep_running=True)
            except Exception:
                pass

    async def open(self, url, wait_ready=True):
        await self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
        await self.page.wait_for_timeout(9000)
        if wait_ready:
            try:
                await self.page.wait_for_function(DOC_READY_JS, timeout=30000)
            except Exception:
                # 公开分享页/未登录页也可能加载编辑器，继续由 info() 判断
                pass
            await self.page.wait_for_timeout(2000)

    async def info(self):
        return await self.page.evaluate(JS_INFO)

    async def text(self):
        return await self.page.evaluate(JS_TEXT)

    async def append(self, text):
        return await self.page.evaluate(JS_APPEND, {"text": text})

    async def replace(self, old, new, replace_all=False):
        """按正文索引定位匹配，用 Range 精确替换（保留其余格式）。

        默认只允许唯一匹配，避免误改多处；确需全部替换时传 replace_all=True。
        """
        text = await self.text()
        spans = []
        start = 0
        while True:
            idx = text.find(old, start)
            if idx < 0:
                break
            spans.append([idx, idx + len(old)])
            start = idx + len(old)
        if not spans:
            return {"error": "not_found"}
        if len(spans) > 1 and not replace_all:
            matches = []
            for i, (s, e) in enumerate(spans[:8], 1):
                left = text[max(0, s - 15):s].replace("\r", " ")
                right = text[e:e + 15].replace("\r", " ")
                matches.append({"occurrence": i, "position": s, "context": left + "【" + old + "】" + right})
            return {
                "error": "multiple_matches",
                "match_count": len(spans),
                "matches": matches,
                "hint": "默认只替换唯一匹配；确需全部替换请加 --all",
            }
        result = await self.page.evaluate(JS_REPLACE, {"spans": spans, "new": new})
        result["replaced_count"] = len(spans)
        result["expected_len"] = len(text) + (len(new) - len(old)) * len(spans)
        if "afterLen" in result:
            result["verify_ok"] = result["afterLen"] == result["expected_len"]
        return result

    async def save(self):
        return await self.page.evaluate(JS_SAVE)

    async def patch(self, pairs, dry_run=False):
        """按最小化 diff 逐段改稿，每段单独成为一条修订。

        pairs: [(old, new), ...]，每处 old 必须在正文中唯一。
        每改一步都回读全文比对，任一不符立即返回失败（调用方负责 RejectAll 回滚）。
        """
        text = await self.text()
        ops = minimal_ops(text, pairs)
        if dry_run:
            return {"dry_run": True, "ops": ops, "before_len": len(text)}
        current = text
        results = []
        for n, op in enumerate(ops, 1):
            nxt = current[:op["start"]] + op["new"] + current[op["end"]:]
            res = await self.page.evaluate(JS_EDIT_OP, {
                "text": current,
                "start": op["start"],
                "old": op["old"],
                "new": op["new"],
                "expect": nxt,
            })
            ok = not res.get("error") and bool(res.get("ok"))
            results.append(dict(op, n=n, ok=ok, res=res))
            if not ok:
                return {"ok": False, "failed_at": n, "ops": results, "after_len": len(current)}
            current = nxt
        return {"ok": True, "ops": results, "after_len": len(current)}

    async def reject_all(self):
        return await self.page.evaluate(JS_REJECT_ALL)


def ensure_editable(info):
    if info.get("signedOut"):
        raise WpsError("当前 Chrome 未登录 WPS，请先运行 login 命令扫码登录")
    if not info.get("textLen"):
        raise WpsError("未读取到文档正文：%s" % info.get("error", "未知原因"))
    if info.get("canComment") and not info.get("canEdit"):
        raise WpsError("当前账号对该文档只有评论权限，无法修改；请让文档所有者授予编辑权限")
