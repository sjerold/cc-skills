"""
从 docx 文件中提取嵌入图片

功能:
- 英文命名: image_001.png, image_002.png, ...
- 基于 embed ID 去重，避免同一图片重复提取
- 默认输出到 docx同目录/文字版/<文档名>/pic/ 目录
- 可通过 --output-dir 指定输出目录（处理WPS云盘场景）
- 自动处理中文路径：先复制到临时目录，处理后再移回

用法:
    python extract_images.py <docx文件路径> [--output-dir <输出目录>]

示例:
    # 默认输出到docx同目录
    python extract_images.py test.docx

    # WPS云盘场景：复制到本地处理，输出到原始目录
    python extract_images.py C:\Downloads\test.docx --output-dir "C:\WPSDrive\...\智能合约\文字版\test"
"""

import os
import sys
import shutil
import tempfile
import argparse
from pathlib import Path
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from PIL import Image
import io


def get_embed_id(drawing_element):
    """从 drawing XML 元素中提取 embed ID"""
    nsmap = {
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    }

    blips = drawing_element.findall('.//a:blip', nsmap)
    if blips:
        embed = blips[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
        return embed
    return None


def extract_image_from_blip(doc, blip_element, pic_dir, count):
    """从 blip 元素提取图片并保存"""
    nsmap = {
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    }

    embed_id = blip_element.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
    if not embed_id:
        return count

    # 获取图片数据
    rel = doc.part.rels[embed_id]
    image_part = rel.target_part
    image_bytes = image_part.blob

    # 确定扩展名
    content_type = image_part.content_type
    ext_map = {
        'image/png': '.png',
        'image/jpeg': '.png',
        'image/jpg': '.png',
        'image/gif': '.png',
        'image/bmp': '.png',
        'image/tiff': '.png',
        'image/x-emf': '.emf',
        'image/x-wmf': '.wmf',
    }
    ext = ext_map.get(content_type, '.png')

    # 如果是非 PNG 格式，转换为 PNG
    if ext != '.png':
        try:
            img = Image.open(io.BytesIO(image_bytes))
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            image_bytes = buf.getvalue()
        except Exception:
            pass

    # 保存文件，使用英文命名
    count += 1
    filename = f"image_{count:03d}.png"
    filepath = os.path.join(pic_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)

    return count


def process_element(doc, element, pic_dir, count, seen_embeds):
    """处理一个元素（段落或表格）中的图片"""
    nsmap = {
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    }

    blips = element.findall('.//a:blip', nsmap)
    for blip in blips:
        embed_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
        if embed_id and embed_id not in seen_embeds:
            seen_embeds.add(embed_id)
            count = extract_image_from_blip(doc, blip, pic_dir, count)

    return count


def extract_images(docx_path, output_dir=None):
    """从 docx 文件提取所有图片

    Args:
        docx_path: docx文件路径
        output_dir: 可选输出目录，如不指定则使用docx同目录的文字版/<文档名>
    """
    if not os.path.isfile(docx_path):
        print(f"错误: 文件不存在 {docx_path}")
        sys.exit(1)

    # 原始路径信息
    basename = Path(docx_path).stem
    doc_dir = os.path.dirname(os.path.abspath(docx_path))

    # 确定输出目录
    if output_dir:
        final_md_dir = output_dir
    else:
        final_md_dir = os.path.join(doc_dir, "文字版", basename)
    final_pic_dir = os.path.join(final_md_dir, "pic")

    # 创建临时目录（不含中文路径）
    temp_dir = tempfile.mkdtemp(prefix="docx_extract_")
    temp_docx = os.path.join(temp_dir, "temp.docx")

    try:
        # 复制 docx 到临时目录
        shutil.copy2(docx_path, temp_docx)
        print(f"已复制到临时目录处理中文路径")

        # 在临时目录处理
        doc = Document(temp_docx)

        # 临时输出目录
        temp_pic_dir = os.path.join(temp_dir, "pic")
        os.makedirs(temp_pic_dir, exist_ok=True)

        seen_embeds = set()
        count = 0

        # 遍历文档中的所有块级元素（段落和表格）
        nsmap = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        }

        body = doc.element.body
        for child in body:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

            if tag == 'p':
                # 段落
                count = process_element(doc, child, temp_pic_dir, count, seen_embeds)
            elif tag == 'tbl':
                # 表格
                count = process_element(doc, child, temp_pic_dir, count, seen_embeds)

        # 清空已有图片（避免残留）
        if os.path.exists(final_pic_dir):
            for f in os.listdir(final_pic_dir):
                os.remove(os.path.join(final_pic_dir, f))
        else:
            os.makedirs(final_pic_dir, exist_ok=True)

        # 将图片从临时目录移到最终目录
        for f in os.listdir(temp_pic_dir):
            shutil.move(os.path.join(temp_pic_dir, f), os.path.join(final_pic_dir, f))

        print(f"提取完成: 共 {count} 张图片")
        print(f"输出目录: {final_pic_dir}")

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)

    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从docx提取图片")
    parser.add_argument("docx_path", help="docx文件路径")
    parser.add_argument("--output-dir", "-o", help="输出目录（默认为docx同目录的文字版/<文档名>）")
    args = parser.parse_args()

    extract_images(args.docx_path, args.output_dir)
