# -*- coding: utf-8 -*-
"""
limg2pimg —— 长图按页智能切分

把手机滚动截屏得到的长图（一屏一页的 PDF 阅读界面），按页面边界切成单页图片。

判据（由粗到细，逐级确认）：
  1. 行投影找空白缝      —— 页面之间必然有一条纯白窄带
  2. 缝后第一个窄带聚类  —— 每页顶部的页眉是同一行文字，宽高与内部结构高度一致
  3. 页码 OCR 校验       —— 只对每页页脚做小图 OCR，确认页码单调递增
  4. 页高先验            —— 已知页高后只查期望位置，OCR 次数降到每页 1 次

为什么不能只看空白：
  实测同一张图里，页间缝只有 270~330px，而末页内部的留白有 961px。
  纯空白阈值会把一页切成两页，所以必须引入页眉/页码这类语义锚点。

用法：
    python split_pages.py <长图> [--out-dir DIR] [--ocr auto|on|off]

输出：
    <stem>_p01.jpg … <stem>_pNN.jpg
    <stem>_pages.json   # 每页的 y 范围、页码、置信度
"""

import os
import re
import sys
import json
import argparse

import numpy as np
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


# ---------------------------------------------------------------- 几何工具

def load_gray(path):
    return np.asarray(Image.open(path).convert("L"))


def row_ink(gray, thr):
    """每行暗色像素数。等价于把长图横切成 H 条 1px 窄图后逐条统计，
    但不需要真的切文件。"""
    return (gray < thr).sum(axis=1)


def find_blank_runs(ink, width, min_len):
    """连续空白的行区间 [(y0, y1), ...]"""
    blank = ink <= max(2, int(width * 0.003))
    runs, i, h = [], 0, len(blank)
    while i < h:
        if blank[i]:
            j = i
            while j + 1 < h and blank[j + 1]:
                j += 1
            if j - i + 1 >= min_len:
                runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs


def first_band_after(gray, y0, y1, thr):
    """从 y0 起找第一个内容带 (a, b)"""
    h = gray.shape[0]
    y1 = min(h, y1)
    a = None
    for y in range(max(0, y0), y1):
        has = (gray[y] < thr).sum() > 2
        if has and a is None:
            a = y
        elif not has and a is not None:
            return a, y - 1
    return (a, y1 - 1) if a is not None else None


def last_thin_band(gray, y0, y1, thr, lo=8, hi=40):
    """[y0, y1) 内最后一个高度在 [lo, hi] 的内容带。

    页脚是「页码 + 版本号」一行小字，高度 14~20px 且下方留白充足；
    比它更薄的（1~3px）是渲染噪点、比它更厚的是正文段落，都要排除。"""
    best, y, y1 = None, y0, min(gray.shape[0], y1)
    while y < y1:
        b = first_band_after(gray, y, y1, thr)
        if not b:
            break
        bh = b[1] - b[0] + 1
        if lo <= bh <= hi:
            best = b
        y = b[1] + 1
    return best


def band_extent(gray, a, b, thr):
    """内容带的水平范围（像素），用于消除截图拼接造成的整体横向抖动"""
    cols = np.where((gray[a:b + 1] < thr).any(axis=0))[0]
    if len(cols) == 0:
        return 0, gray.shape[1] - 1
    return int(cols[0]), int(cols[-1])


def band_signature(gray, a, b, thr, bins=256):
    """内容带的列墨迹剖面，按内容边界裁齐后重采样。

    裁齐这一步很关键：手机滚动截屏拼接时整页会左右抖动上百像素，
    若按绝对坐标取剖面，同一行页眉的相似度会掉到 0.5，聚类就散了。"""
    seg = gray[a:b + 1] < thr
    col = seg.sum(axis=0).astype(np.float64)
    x0, x1 = band_extent(gray, a, b, thr)
    col = col[x0:x1 + 1]
    if len(col) == 1:
        col = np.repeat(col, 2)
    s = np.interp(np.linspace(0, len(col) - 1, bins), np.arange(len(col)), col)
    n = np.linalg.norm(s)
    return s / n if n > 0 else s


def cosine(x, y):
    return float(np.dot(x, y))


# ---------------------------------------------------------------- 主流程

class LongImageSplitter:
    H_MIN = 8          # 页高下限（像素），低于此值不可能是独立一页
    HEAD_SIM = 0.90    # 页眉签名余弦阈值
    BAND_MAX_H = 60    # 页眉候选的最大高度
    DEDUPE_SIM = 0.98  # 拼接残影判定的相似度阈值

    def __init__(self, path, thr=170, min_gap=120, verbose=True):
        self.path = path
        self.thr = thr
        self.min_gap = min_gap
        self.verbose = verbose
        self.gray = load_gray(path)
        self.h, self.w = self.gray.shape
        self.ink = row_ink(self.gray, thr)
        self.gaps = find_blank_runs(self.ink, self.w, min_gap)
        self.pages = []
        self.meta = {}

    # -- 日志
    def log(self, msg):
        if self.verbose:
            print(msg)

    # -- 孤立小带：页码、项目符号、装饰短线
    def _is_stray_band(self, a, b):
        """宽度远小于页面宽度的窄带。

        页眉是整行标题，宽度必然可观；这类小带被误当页眉时，
        它所在的那条缝就切不出页，一整页会和下一页粘在一起。"""
        x0, x1 = band_extent(self.gray, a, b, self.thr)
        return (x1 - x0 + 1) < max(24, int(self.w * 0.05))

    def _blank_run_before(self, y, limit):
        """y 上方紧邻的连续空白行区间 (y0, y1)；向上扫描不越到 limit。"""
        blank = self.ink <= max(2, int(self.w * 0.003))
        t = y - 1
        while t > limit and blank[t]:
            t -= 1
        return t + 1, y - 1

    # -- 第一步：页眉聚类
    def detect_headers(self):
        cands = []
        for (a, b) in self.gaps:
            band = first_band_after(self.gray, b + 1, b + 1 + 400, self.thr)
            if not band:
                continue
            gap = (a, b)
            # 缝后第一个内容带未必是页眉：页码也常落在缝的下沿，而且常被行投影
            # 拆成「5px 上沿 + 13px 字形」两段（实测）。把它当页眉，这一页就切不出来，
            # 会和下一页粘成 1.5 页。所以连续跳过这类孤立小带，直到遇到实质内容带。
            for _ in range(4):
                if not self._is_stray_band(*band):
                    break
                nxt = first_band_after(self.gray, band[1] + 1, b + 1 + 400, self.thr)
                if not nxt:
                    break
                band = nxt
            ba, bb = band
            if bb - ba + 1 > self.BAND_MAX_H:
                continue
            x0, x1 = band_extent(self.gray, ba, bb, self.thr)
            # 分界始终取「页眉正上方」那条缝，而不是最初命中的缝
            run = self._blank_run_before(ba, b)
            if run[1] >= run[0] and run[1] - run[0] + 1 >= 5:
                gap = run
            cands.append({
                "gap": gap,
                "band": (ba, bb),
                "h": bb - ba + 1,
                "width": x1 - x0 + 1,
                "sig": band_signature(self.gray, ba, bb, self.thr),
            })

        # 同一条页眉可能被多条缝命中（缝中间的噪声小带把一条缝拆成了两条）。
        # 按页眉位置去重：组内若出现间距 0，页高一致性检查会整组被否掉。
        uniq = {}
        for c in cands:
            uniq.setdefault(c["band"][0], c)
        cands = [uniq[k] for k in sorted(uniq)]

        # 并查集聚类：页眉之间可能因抗锯齿/水印略有差异，
        # 用传递闭包把同一模板的带连成一组。
        n = len(cands)
        parent = list(range(n))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i, j):
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[rj] = ri

        for i in range(n):
            for j in range(i + 1, n):
                sim = cosine(cands[i]["sig"], cands[j]["sig"])
                if sim >= self.HEAD_SIM:
                    union(i, j)

        groups = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(cands[i])
        groups = sorted(groups.values(), key=len, reverse=True)

        # 页眉组的附加约束：成员高度接近、水平宽度接近，且间距足够大
        best = None
        for g in groups:
            if len(g) < 3:
                continue
            hs = [c["h"] for c in g]
            ws = [c["width"] for c in g]
            if max(hs) - min(hs) > 12:
                continue
            if max(ws) - min(ws) > self.w * 0.08:
                continue
            # 页眉是一整行标题，宽度必然可观。21px 宽的小短线是页码、项目符号
            # 之类的噪声，误认成页眉会把整张图切塌（曾把 28 页的图切成 6 页）。
            if min(ws) < 0.15 * self.w:
                continue
            ys = sorted(c["band"][0] for c in g)
            if min(np.diff(ys)) < 0.5 * float(np.median(np.diff(ys))):
                continue
            best = g
            break

        self.meta["header_count"] = len(best) if best else 0
        if best:
            self.log(f"[页眉] 命中 {len(best)} 处，模板高度 {best[0]['h']}px，"
                     f"宽度 {best[0]['width']}px")
            return sorted(best, key=lambda c: c["gap"][0])
        return []

    # -- 第二步：顶部 App 栏
    def detect_top(self, headers=None):
        lim = int(self.h * 0.05)
        # 顶部文本带数量：状态栏 + 标题栏，带工具栏时是 3 段以上
        cnt, y, inside, band2_end = 0, 0, False, 0
        while y < lim:
            has = self.ink[y] > 2
            if has and not inside:
                cnt += 1
                inside = True
            elif not has:
                inside = False
                if cnt == 2:
                    band2_end = y
            y += 1
        if cnt < 2:
            return 0
        first = self.ink[:max(1, int(self.h * 0.02))].max()
        if first <= 2:
            return 0
        for (a, b) in self.gaps:
            if b < lim and (b - a + 1) >= 200:
                self.log(f"[顶部] 检测到 App 工具栏，内容起点 {b + 1}")
                return b + 1
        # 有些截图不显示 WPS 工具栏，App 界面只剩状态栏 + 标题栏。它与正文之间
        # 的缝只有 100~150px —— 比页间缝(120)还窄，压根不在 self.gaps 里，上面
        # 那条判据必然落空，整条手机界面就被当成首页内容留下来（实测首页多出
        # 330px）。改用页眉模板倒推：往下扫，第一个长宽都对得上页眉的窄带就是
        # 正文起点。只匹配到页眉本身，即便误命中，丢的也只是它上方的留白。
        if headers and band2_end:
            mh = float(np.median([c["h"] for c in headers]))
            mw = float(np.median([c["width"] for c in headers]))
            y = band2_end
            for _ in range(6):
                band = first_band_after(self.gray, y, lim, self.thr)
                if not band:
                    break
                ba, bb = band
                x0, x1 = band_extent(self.gray, ba, bb, self.thr)
                if (bb - ba + 1 <= self.BAND_MAX_H
                        and 0.7 * mh <= bb - ba + 1 <= 1.4 * mh
                        and 0.8 * mw <= x1 - x0 + 1 <= 1.25 * mw):
                    self.log(f"[顶部] 无工具栏，按页眉模板反推，内容起点 {ba}")
                    return ba
                y = bb + 1
        return 0

    # -- 第三步：末页页脚与底部 UI
    def detect_bottom(self, last_header_y):
        """末页页脚之后就是 App 的评论区，按页脚位置裁掉"""
        tail_start = last_header_y if last_header_y is not None else int(self.h * 0.6)
        band = last_thin_band(self.gray, tail_start, self.h, self.thr)
        if not band:
            return self.h
        ba, bb = band
        if ba < self.h * 0.5:          # 只接受真正的页面末尾
            return self.h
        nxt = first_band_after(self.gray, bb + 1, self.h, self.thr)
        gap_len = (nxt[0] - bb - 1) if nxt else (self.h - bb - 1)
        cut = bb + 1 + max(24, min(gap_len // 2, 60))
        self.log(f"[底部] 末页页脚 {ba}-{bb}，裁到 {cut}")
        return cut

    # -- 汇总分页边界
    def compute_bounds(self):
        headers = self.detect_headers()
        top = self.detect_top(headers)
        last_header_y = headers[-1]["band"][0] if headers else None
        bottom = self.detect_bottom(last_header_y)

        if headers:
            # 每个页眉前面那条缝，中点就是上一页与本页的分界
            cuts = [(g["gap"][0] + g["gap"][1]) // 2 for g in headers]
            bounds = [top] + cuts + [bottom]
            mode = "header"
        else:
            bounds = self._fallback_bounds(top, bottom)
            mode = "fallback"

        pages = []
        for i in range(len(bounds) - 1):
            y0, y1 = int(bounds[i]), int(bounds[i + 1])
            if y1 - y0 < self.H_MIN:
                continue
            pages.append({"page": len(pages) + 1, "y0": y0, "y1": y1,
                          "height": y1 - y0})
        self.pages = pages
        self.meta.update({"mode": mode, "image": [self.w, self.h],
                          "top": top, "bottom": bottom})
        return pages

    def _fallback_bounds(self, top, bottom):
        """没有可聚类的页眉时：用页间缝 + 页高一致性兜底"""
        mids = [(a + b) // 2 for (a, b) in self.gaps if a > top and b < bottom]
        if not mids:
            return [top, bottom]
        diffs = np.diff(mids)
        diffs = diffs[diffs > 0]
        if len(diffs) == 0:
            return [top] + mids + [bottom]
        mode_h = float(np.median(diffs))
        keep = [mids[0]]
        for m in mids[1:]:
            if m - keep[-1] >= 0.6 * mode_h:
                keep.append(m)
        self.log(f"[回退] 无页眉模板，按空白缝切分，估计页高 {mode_h:.0f}px")
        return [top] + keep + [bottom]

    # -- 拼接残影
    def find_duplicates(self, y0, y1):
        """手机滚动截屏在每段停留处会重复拼接一次，表现为同一页内
        「上面一段内容」紧接着又出现一遍。返回要删除的绝对 y 区间。

        判据：连续多个内容带与前面某处一一对应且间距一致，
        单个孤立相似带不算（正文里同款表格行很常见）。"""
        bands, y = [], y0
        while y < y1:
            b = first_band_after(self.gray, y, y1, self.thr)
            if not b:
                break
            bands.append(b)
            y = b[1] + 1
        if len(bands) < 4:
            return []
        sigs = [band_signature(self.gray, a, b, self.thr) for a, b in bands]

        dup = {}
        for i in range(len(bands)):
            for j in range(i + 1, len(bands)):
                if cosine(sigs[i], sigs[j]) >= self.DEDUPE_SIM:
                    dup[i] = j
                    break

        ranges = []
        i = 0
        while i < len(bands):
            if i not in dup:
                i += 1
                continue
            j = last_j = dup[i]
            k = i
            while (k + 1) in dup and dup[k + 1] == last_j + 1:
                k += 1
                last_j += 1
            span = k - i + 1
            # 单个/两个相似带在正文里太常见（表格行、流程图的箭头方框），
            # 只有连成一段、并且占版面足够比例的才算拼接残影。
            if span >= 3:
                dys = [bands[dup[m]][0] - bands[m][0] for m in range(i, k + 1)]
                a, b = bands[j][0], bands[last_j][1]
                if max(dys) - min(dys) <= 0.05 * float(np.median(dys)) \
                        and (b - a + 1) >= 0.04 * (y1 - y0):
                    ranges.append((int(a), int(b)))
            i = k + 1
        return ranges

    def dedupe(self):
        total = 0
        for p in self.pages:
            rng = self.find_duplicates(p["y0"], p["y1"])
            p["dedupe_ranges"] = rng
            if rng:
                removed = sum(b - a + 1 for a, b in rng)
                total += removed
                self.log(f"  第 {p['page']} 页：移除拼接残影 {removed}px")
        if total:
            self.log(f"[去重] 共移除 {total}px 重复残影")
        else:
            self.log("[去重] 未发现拼接残影")

    # -- 第四步：页码 OCR
    NUM_RE = re.compile(r"(?<!\d)(\d{1,3})(?!\d)")
    # V01R01E004_20260722 这类版本号整体剔除，避免把 01/004 当成页码
    VER_RE = re.compile(r"[A-Za-z0-9_]*[A-Za-z]\d{1,3}[A-Za-z]\d{2,4}[A-Za-z]?\d*[A-Za-z0-9_]*")

    def _footer_band(self, p):
        """页面底部 15% 内最下面那行小字"""
        y0, y1 = p["y0"], p["y1"]
        return last_thin_band(self.gray, y1 - int((y1 - y0) * 0.15), y1, self.thr)

    def ocr_pages(self):
        """页脚裁成一行行小图、纵向拼成一张大图，一次 OCR 全部识别。

        逐页 OCR 每页要 1.4~2.9s（14 页约 30s）；拼成一张只跑一次检测，
        整轮 4~5s，且放大会让小号页码更容易被检出。"""
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception:
            self.log("[OCR] 未安装 rapidocr_onnxruntime，跳过页码识别")
            return
        import time

        im = Image.open(self.path).convert("RGB")
        for p in self.pages:
            p["page_num"] = None
            p["footer_text"] = ""
        bands = [self._footer_band(p) for p in self.pages]
        scale, gap = 2, 80
        pieces, offsets = [], []
        cur = 0
        for b in bands:
            if not b:
                continue
            a, bb = b
            crop = im.crop((0, max(0, a - 8), self.w, bb + 9))
            crop = crop.resize((crop.width * scale, crop.height * scale))
            pieces.append(crop)
            offsets.append((cur, cur + crop.height))
            cur += crop.height + gap
        if not pieces:
            self.log("[OCR] 未找到页脚行")
            return

        total = sum(pc.height for pc in pieces) + gap * (len(pieces) - 1)
        canvas = Image.new("RGB", (self.w * scale, total), "white")
        y = 0
        for pc in pieces:
            canvas.paste(pc, (0, y))
            y += pc.height + gap

        t0 = time.time()
        res, _ = get_ocr_engine()(np.asarray(canvas))
        texts = [[] for _ in pieces]
        for box, txt, _score in (res or []):
            cy = sum(pt[1] for pt in box) / 4
            idx, best_d = None, 1e18
            for i, (o0, o1) in enumerate(offsets):
                d = 0 if o0 <= cy <= o1 else min(abs(cy - o0), abs(cy - o1))
                if d < best_d:
                    best_d, idx = d, i
            if idx is not None:
                texts[idx].append(txt)
        self.log(f"[OCR] {len(pieces)} 行页脚一次识别，用时 {time.time() - t0:.1f}s")

        # 归回页码
        page_objs = [p for p, b in zip(self.pages, bands) if b]
        for p in page_objs:
            p["page_num"] = None
            p["footer_text"] = ""
        for p, ts in zip(page_objs, texts):
            p["footer_text"] = " | ".join(ts)
            p["page_num"] = self._parse_num(" ".join(ts))

        detected = [(p["page"], p["page_num"]) for p in page_objs if p["page_num"]]
        self.meta["page_numbers_detected"] = len(detected)
        if not detected:
            self.log("[OCR] 未识别到页码，使用顺序编号")
            return

        # 文档的页码不一定从 1 开始（封面常不计页码），用检出的页码反推偏移量
        deltas = [num - idx for idx, num in detected]
        offset = max(set(deltas), key=deltas.count)
        mono = True
        last = -1
        for p in self.pages:
            guess = p["page"] + offset
            if guess < 1:
                guess = p["page"]
            if p["page_num"] is not None and p["page_num"] != guess:
                mono = False
            if p["page_num"] is None:
                p["page_num_inferred"] = guess
            if p["page_num"] is not None:
                if last >= 0 and p["page_num"] <= last:
                    mono = False
                last = p["page_num"]
        self.meta["page_number_offset"] = offset
        self.meta["page_number_monotonic"] = mono
        self.log(f"[OCR] 检出 {len(detected)}/{len(page_objs)} 个页码，"
                 f"页码偏移 {offset:+d}{'，单调递增 ✓' if mono else '，存在冲突'}")

    def _parse_num(self, text):
        if not text:
            return None
        cleaned = self.VER_RE.sub(" ", text)          # 去掉 V01R01E004_20260722 这类版本号
        nums = [int(x) for x in self.NUM_RE.findall(cleaned)]
        nums = [n for n in nums if 1 <= n <= 999]
        return nums[0] if nums else None

    # -- 第五步：切图
    def _page_image(self, im, p, pad=0):
        y0 = max(0, p["y0"] - pad)
        y1 = min(self.h, p["y1"] + pad)
        cuts = [r for r in p.get("dedupe_ranges", []) if y0 <= r[0] and r[1] <= y1]
        if not cuts:
            return im.crop((0, y0, self.w, y1))
        parts, cur = [], y0
        for a, b in sorted(cuts):
            if a > cur:
                parts.append(im.crop((0, cur, self.w, a)))
            cur = max(cur, b)
        if cur < y1:
            parts.append(im.crop((0, cur, self.w, y1)))
        total = sum(x.height for x in parts)
        canvas = Image.new(im.mode, (self.w, total))
        y = 0
        for part in parts:
            canvas.paste(part, (0, y))
            y += part.height
        return canvas

    def export(self, out_dir, fmt="jpg", quality=92, pad=0, prefix=""):
        os.makedirs(out_dir, exist_ok=True)
        # 清掉上一轮残留的 p*.jpg：同一份长图重切时若页数变少（改了 --thr 等），
        # 旧的 p15.jpg 会留在目录里，按文件名排序就直接多出几页不存在的内容。
        # 旧清单一起清掉——输出目录默认只留图片。
        # 多张长图共用同一个输出目录时（flat 模式）文件名带 <图片名>_ 前缀，
        # 清理必须限定在本图自己的文件上，否则会把别的图切好的页删掉。
        stem = os.path.splitext(os.path.basename(self.path))[0]
        old_manifest = f"{stem}_pages.json"
        stale = re.compile(r"^" + re.escape(prefix) + r"p\d+\.(?:jpg|jpeg|png)$",
                           re.IGNORECASE)
        for name in os.listdir(out_dir):
            if stale.match(name) or name == old_manifest:
                try:
                    os.remove(os.path.join(out_dir, name))
                except OSError:
                    pass
        im = Image.open(self.path)
        digits = max(2, len(str(len(self.pages))))
        files = []
        for p in self.pages:
            img = self._page_image(im, p, pad=pad)
            # 文件名按阅读顺序编号。文档自身的页码可能从正文才起算（前面有封面、
            # 修订记录），直接拿它命名会和顺序号撞名，所以页码只记进清单。
            # 零填充保证字典序与阅读顺序一致（p02 < p10）。
            tag = f"{prefix}p{p['page']:0{digits}d}"
            out = os.path.join(out_dir, f"{tag}.{fmt}")
            if fmt.lower() in ("jpg", "jpeg"):
                img.convert("RGB").save(out, quality=quality, subsampling=0)
            else:
                img.save(out)
            p["file"] = os.path.basename(out)
            p["height_out"] = img.height
            files.append(out)
            self.log(f"  {os.path.basename(out):32s} y={p['y0']}-{p['y1']}  h={img.height}")
        return files

    def save_manifest(self, out_dir):
        stem = os.path.splitext(os.path.basename(self.path))[0]
        path = os.path.join(out_dir, f"{stem}_pages.json")
        data = dict(self.meta)
        data["source"] = os.path.abspath(self.path)
        data["page_count"] = len(self.pages)
        data["pages"] = self.pages
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path


# ---------------------------------------------------------------- CLI

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

_OCR_ENGINE = None


def get_ocr_engine():
    """OCR 引擎初始化要 1~2 秒，批量处理多张长图时复用同一个实例"""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def natural_key(name):
    """CBETS2 < CBETS10，按数字大小而不是字符排序"""
    return [(0, int(t)) if t.isdigit() else (1, t.lower())
            for t in re.split(r"(\d+)", name)]


def collect_images(path):
    files = [os.path.join(path, n) for n in os.listdir(path)
             if os.path.isfile(os.path.join(path, n))
             and os.path.splitext(n)[1].lower() in IMAGE_EXT]
    return sorted(files, key=lambda p: natural_key(os.path.basename(p)))


def aspect_ratio(path):
    with Image.open(path) as im:
        w, h = im.size
    return h / float(w) if w else 0.0


def process_one(path, out_dir, args, log, prefix=""):
    sp = LongImageSplitter(path, thr=args.thr, min_gap=args.min_gap,
                           verbose=not args.quiet)
    pages = sp.compute_bounds()
    log(f"  {sp.w}x{sp.h} → {len(pages)} 页")

    if not args.no_dedupe:
        sp.dedupe()

    if args.ocr != "off":
        try:
            import importlib.util
            have = importlib.util.find_spec("rapidocr_onnxruntime") is not None
        except Exception:
            have = False
        if have or args.ocr == "on":
            sp.ocr_pages()

    out_dir = out_dir or os.path.join(
        os.path.dirname(os.path.abspath(path)),
        os.path.splitext(os.path.basename(path))[0] + "_pages")
    sp.export(out_dir, fmt=args.format, quality=args.quality, pad=args.pad,
              prefix=prefix)
    if getattr(args, "manifest", False):
        manifest = sp.save_manifest(out_dir)
        log(f"  → {out_dir}（清单 {os.path.basename(manifest)}）")
    else:
        log(f"  → {out_dir}")
    return {
        "source": os.path.abspath(path),
        "out_dir": os.path.abspath(out_dir),
        "page_count": len(sp.pages),
        "mode": sp.meta.get("mode"),
        "size": [sp.w, sp.h],
    }


def main():
    ap = argparse.ArgumentParser(
        description="把 PDF 滚动截屏长图按页切分成单页图片；可传单张图片或整个目录")
    ap.add_argument("input", help="长图路径，或包含多张长图的目录")
    ap.add_argument("--out-dir", default=None,
                    help="输出目录（目录模式下默认把所有长图的页平铺进这个目录）")
    ap.add_argument("--ocr", choices=["auto", "on", "off"], default="auto",
                    help="页码识别：auto=装了就开（默认），on=强制，off=关闭")
    ap.add_argument("--min-gap", type=int, default=120, help="页面间最小空白高度（像素）")
    ap.add_argument("--thr", type=int, default=170, help="灰度阈值，越低越排除浅色水印")
    ap.add_argument("--format", default="jpg", choices=["jpg", "png"], help="输出格式")
    ap.add_argument("--quality", type=int, default=92, help="JPG 质量")
    ap.add_argument("--pad", type=int, default=0, help="每页上下额外保留的像素")
    ap.add_argument("--no-dedupe", action="store_true",
                    help="关闭拼接残影去重（默认开启）")
    ap.add_argument("--min-aspect", type=float, default=2.0,
                    help="目录模式下只处理高宽比 ≥ 此值的图（默认 2.0，过滤普通图片）")
    ap.add_argument("--per-dir", action="store_true",
                    help="目录模式下每张长图单独建 <图片名>_pages 子目录"
                         "（默认全部页平铺在同一目录，文件名加 <图片名>_ 前缀）")
    ap.add_argument("--manifest", action="store_true",
                    help="额外输出 JSON 清单（默认不输出，输出目录只留图片）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"路径不存在：{args.input}")

    def log(msg):
        if not args.quiet:
            print(msg)

    # 单张图片
    if os.path.isfile(args.input):
        info = process_one(args.input, args.out_dir, args, log)
        log(f"完成：{info['page_count']} 页")
        return

    # 目录：按文件名自然排序后逐张处理，每张一个子目录
    files = collect_images(args.input)
    if not files:
        sys.exit(f"目录下没有图片：{args.input}")

    # 目录模式的默认输出目录：与输入目录同级的 <目录名>_pages，
    # 不再往源目录里塞子目录，避免把待处理的长图和产出混在一起。
    root = args.out_dir or (os.path.abspath(args.input).rstrip("\\/") + "_pages")
    results, skipped, failed = [], [], []
    for i, f in enumerate(files, 1):
        name = os.path.basename(f)
        try:
            ratio = aspect_ratio(f)
        except Exception as e:
            failed.append({"source": name, "error": f"{type(e).__name__}: {e}"})
            log(f"[{i}/{len(files)}] 跳过 {name}（无法读取：{e}）")
            continue
        if ratio < args.min_aspect:
            skipped.append({"source": name, "aspect": round(ratio, 2)})
            log(f"[{i}/{len(files)}] 跳过 {name}（高宽比 {ratio:.2f}，不是长图）")
            continue
        stem = os.path.splitext(name)[0]
        # 目录模式默认平铺：所有长图的页都写进同一个目录，文件名加 <图片名>_ 前缀，
        # 既不会互相覆盖，按文件名排序也仍是阅读顺序（CBETS32_p28 < CBETS33_p01）。
        if args.per_dir:
            out_dir, prefix = os.path.join(root, stem + "_pages"), ""
        else:
            out_dir, prefix = root, stem + "_"
        log(f"[{i}/{len(files)}] {name}")
        # 单张失败不中断整批：一张损坏的图不该让后面十几张都没机会处理
        try:
            results.append(process_one(f, out_dir, args, log, prefix=prefix))
        except Exception as e:
            failed.append({"source": name, "error": f"{type(e).__name__}: {e}"})
            log(f"  ✗ 处理失败：{type(e).__name__}: {e}")

    if args.manifest:
        index_path = os.path.join(root, "limg2pimg_index.json")
        with open(index_path, "w", encoding="utf-8") as fh:
            json.dump({"directory": os.path.abspath(args.input),
                       "images": results, "skipped": skipped, "failed": failed},
                      fh, ensure_ascii=False, indent=2)
    else:
        # 上一轮留下的汇总清单也清掉，输出目录保持"只有图片"
        stale_index = os.path.join(root, "limg2pimg_index.json")
        if os.path.isfile(stale_index):
            try:
                os.remove(stale_index)
            except OSError:
                pass

    log(f"\n完成 {len(results)} 张长图，跳过 {len(skipped)} 张"
        + (f"，失败 {len(failed)} 张" if failed else ""))
    if args.manifest:
        log(f"汇总清单：{index_path}")


if __name__ == "__main__":
    main()
