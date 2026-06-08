"""
从混合图片中分离图形和文字区域

核心思路：
1. PaddleOCR 检测所有文字区域及其边界框
2. OpenCV 检测图形元素（矩形框、连线）
3. 合并分析：判断是纯文字、纯图形还是混合
4. 混合类：裁剪出图形区域，保留文字标注

用法:
    python crop_graphics.py <图片路径> <输出目录>

输出:
    - <name>_graphic.png  裁剪后的图形部分
    - <name>_annotated.json  文字区域标注
"""

import os
import sys
import json
import cv2
import numpy as np
from paddleocr import PaddleOCR


def detect_text_regions(img_path, ocr):
    """OCR 检测所有文字区域"""
    result = ocr.ocr(img_path, cls=True)
    regions = []
    if result and result[0]:
        for line in result[0]:
            bbox_pts = line[0]  # 四个角点
            text = line[1][0]
            confidence = line[1][1]
            xs = [int(p[0]) for p in bbox_pts]
            ys = [int(p[1]) for p in bbox_pts]
            x, y = min(xs), min(ys)
            bw, bh = max(xs) - min(xs), max(ys) - min(ys)
            regions.append({
                "text": text,
                "bbox": [x, y, bw, bh],
                "corners": [[int(p[0]), int(p[1])] for p in bbox_pts],
                "confidence": confidence,
                "area": bw * bh
            })
    return regions


def detect_graphic_regions(img):
    """
    使用 OpenCV 检测图形区域（流程图框、连线、形状）

    策略：
    1. 边缘检测找线条
    2. 霍夫线变换找直线（流程图连接线）
    3. 轮廓检测找矩形框
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    # 方法1: Canny 边缘检测 + 形态学
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated_edges = cv2.dilate(edges, kernel, iterations=2)

    # 方法2: 自适应阈值检测深色元素
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    dilated_binary = cv2.dilate(binary, kernel, iterations=2)

    # 合并两种检测结果
    combined = cv2.bitwise_or(dilated_edges, dilated_binary)

    # 查找轮廓
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    graphic_bboxes = []
    min_graphic_area = (w * h) * 0.005  # 最小占图面积 0.5%

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_graphic_area:
            continue

        x, y, bw, bh = cv2.boundingRect(cnt)
        aspect_ratio = bw / float(bh)

        # 排除纯文字轮廓（文字通常较窄或较小）
        # 保留：较大的块、近似方形的块、细长的线
        is_graphic = False

        # 大矩形/方形 → 流程图框
        if area > (w * h) * 0.01 and 0.5 < aspect_ratio < 2.0:
            is_graphic = True
        # 细长条 → 连接线
        elif (aspect_ratio > 5.0 or aspect_ratio < 0.2) and area > min_graphic_area:
            is_graphic = True
        # 中等大小的连通区域
        elif area > (w * h) * 0.02:
            is_graphic = True

        if is_graphic:
            graphic_bboxes.append((x, y, bw, bh))

    return graphic_bboxes


def analyze_layout(text_regions, graphic_bboxes, img_w, img_h):
    """
    分析图片布局，判断类型

    返回: ("pure_text" | "pure_graphic" | "mixed", details)
    """
    img_area = img_w * img_h

    # 计算文字覆盖面积
    text_covered = np.zeros((img_h, img_w), dtype=np.uint8)
    for tr in text_regions:
        x, y, bw, bh = tr["bbox"]
        x, y = max(0, x), max(0, y)
        bw = min(bw, img_w - x)
        bh = min(bh, img_h - y)
        if bw > 0 and bh > 0:
            text_covered[y:y + bh, x:x + bw] = 255
    text_area = np.count_nonzero(text_covered)
    text_ratio = text_area / img_area

    # 计算图形覆盖面积
    graphic_covered = np.zeros((img_h, img_w), dtype=np.uint8)
    for gx, gy, gw, gh in graphic_bboxes:
        gx, gy = max(0, gx), max(0, gy)
        gw = min(gw, img_w - gx)
        gh = min(gh, img_h - gy)
        if gw > 0 and gh > 0:
            graphic_covered[gy:gy + gh, gx:gx + gw] = 255
    graphic_area = np.count_nonzero(graphic_covered)
    graphic_ratio = graphic_area / img_area

    # 文字和图形的重叠区域（文字标注在图形上）
    overlap = np.count_nonzero(text_covered & graphic_covered)
    overlap_ratio = overlap / img_area

    # 判断类型
    if graphic_ratio > 0.3 and text_ratio < 0.15:
        layout_type = "pure_graphic"
    elif text_ratio > 0.4 and graphic_ratio < 0.1:
        layout_type = "pure_text"
    elif graphic_ratio > 0.05 and text_ratio > 0.05:
        layout_type = "mixed"
    else:
        # 默认：看哪个占比大
        layout_type = "pure_text" if text_ratio > graphic_ratio else "pure_graphic"

    return layout_type, {
        "text_ratio": round(text_ratio, 3),
        "graphic_ratio": round(graphic_ratio, 3),
        "overlap_ratio": round(overlap_ratio, 3),
        "text_region_count": len(text_regions),
        "graphic_bbox_count": len(graphic_bboxes)
    }


def compute_graphic_crop_bbox(graphic_bboxes, text_regions, img_w, img_h):
    """
    计算图形区域的裁剪边界框

    策略：找到所有图形元素的包围盒，排除纯文字区域
    """
    if not graphic_bboxes:
        return None

    # 合并所有图形边界框
    min_x = min(g[0] for g in graphic_bboxes)
    min_y = min(g[1] for g in graphic_bboxes)
    max_x = max(g[0] + g[2] for g in graphic_bboxes)
    max_y = max(g[1] + g[3] for g in graphic_bboxes)

    # 加边距
    margin = 15
    crop_x = max(0, min_x - margin)
    crop_y = max(0, min_y - margin)
    crop_w = min(img_w - crop_x, (max_x - min_x) + 2 * margin)
    crop_h = min(img_h - crop_y, (max_y - min_y) + 2 * margin)

    return [crop_x, crop_y, crop_w, crop_h]


def crop_and_annotate(img_path, output_dir):
    """处理混合图片"""
    os.makedirs(output_dir, exist_ok=True)

    img = cv2.imread(img_path)
    if img is None:
        print(f"  错误: 无法读取 {img_path}")
        return None

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    name = os.path.splitext(os.path.basename(img_path))[0]

    # 初始化 OCR（只初始化一次）
    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)

    # 步骤1: 检测文字区域
    text_regions = detect_text_regions(img_path, ocr)

    # 步骤2: 检测图形区域
    graphic_bboxes = detect_graphic_regions(img_rgb)

    # 步骤3: 分析布局
    layout_type, layout_info = analyze_layout(text_regions, graphic_bboxes, w, h)

    result = {
        "image": os.path.basename(img_path),
        "original_size": [w, h],
        "layout_type": layout_type,
        "layout_analysis": layout_info,
        "text_regions": text_regions,
        "graphic_bboxes": graphic_bboxes,
    }

    if layout_type == "mixed":
        # 混合类：裁剪图形区域
        crop_bbox = compute_graphic_crop_bbox(graphic_bboxes, text_regions, w, h)
        if crop_bbox:
            cx, cy, cw, ch = crop_bbox
            cropped = img_rgb[cy:cy + ch, cx:cx + cw]
            graphic_path = os.path.join(output_dir, f"{name}_graphic.png")
            cv2.imwrite(graphic_path, cv2.cvtColor(cropped, cv2.COLOR_RGB2BGR))

            # 调整文字区域坐标为相对于裁剪图的坐标
            for tr in result["text_regions"]:
                tr["bbox_relative"] = [
                    tr["bbox"][0] - cx,
                    tr["bbox"][1] - cy,
                    tr["bbox"][2],
                    tr["bbox"][3]
                ]
                # 判断文字是否在图形区域内
                tx, ty = tr["bbox"][0], tr["bbox"][1]
                tr["is_on_graphic"] = (cx <= tx <= cx + cw and cy <= ty <= cy + ch)

            result["crop_bbox"] = crop_bbox
            result["cropped_graphic"] = f"{name}_graphic.png"
            result["cropped_size"] = [cw, ch]

            print(f"  类型: 混合类 (文字{layout_info['text_ratio']:.0%} + 图形{layout_info['graphic_ratio']:.0%})")
            print(f"  图形区域: [{cx}, {cy}, {cw}x{ch}]")
            print(f"  文字区域: {len(text_regions)} 个")
            # 打印文字标注
            for i, tr in enumerate(text_regions[:10]):
                pos = tr["bbox"]
                print(f"    标注[{i+1}]: \"{tr['text']}\" @ ({pos[0]}, {pos[1]})")
            if len(text_regions) > 10:
                print(f"    ... 还有 {len(text_regions) - 10} 个")
            print(f"  裁剪图: {graphic_path}")
        else:
            result["layout_type"] = "pure_text"
            print(f"  类型: 纯文字 (文字{layout_info['text_ratio']:.0%})")

    elif layout_type == "pure_graphic":
        # 纯图形：保留原图，只标注文字
        print(f"  类型: 纯图形 (图形{layout_info['graphic_ratio']:.0%})")
        print(f"  文字标注: {len(text_regions)} 个")
        for i, tr in enumerate(text_regions[:5]):
            print(f"    标注[{i+1}]: \"{tr['text']}\" @ ({tr['bbox'][0]}, {tr['bbox'][1]})")

    else:
        # 纯文字：不需要裁剪
        print(f"  类型: 纯文字 (文字{layout_info['text_ratio']:.0%})")
        # 直接输出OCR文字即可，不需要额外处理

    # 保存标注 JSON
    json_path = os.path.join(output_dir, f"{name}_annotated.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python crop_graphics.py <图片路径> <输出目录>")
        sys.exit(1)
    crop_and_annotate(sys.argv[1], sys.argv[2])
