"""
批量 OCR 处理脚本 - 将 OCR 结果写入文件
"""
import os
import sys
import base64
import json
import urllib.request
import urllib.error
import concurrent.futures

# 添加上级目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from external_ocr import encode_image, get_mime_type, call_api, DEFAULT_PROMPT

def process_and_save(image_path, output_path, model, api_key, prompt):
    """处理单张图片并保存结果"""
    try:
        image_base64 = encode_image(image_path)
        mime_type = get_mime_type(image_path)
        content = call_api(image_base64, mime_type, model, api_key, prompt)

        img_name = os.path.basename(image_path)
        result = f"=== {img_name} ===\n{content}\n"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)

        return image_path, True, content[:100]
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(error_msg)
        return image_path, False, str(e)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, help="图片目录")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--start", type=int, default=1, help="起始编号")
    parser.add_argument("--end", type=int, default=10, help="结束编号")
    parser.add_argument("--model", default="kimi-k2-5", help="模型名称")
    parser.add_argument("--token", default=None, help="API Token")
    args = parser.parse_args()

    api_key = args.token or os.environ.get("SP_TOKEN")
    if not api_key:
        print("错误: 需要 --token 或 SP_TOKEN 环境变量")
        sys.exit(1)

    # 确保输出目录存在
    os.makedirs(args.output_dir, exist_ok=True)

    # 构建图片和输出路径列表
    tasks = []
    for i in range(args.start, args.end + 1):
        img_name = f"image_{i:03d}.png"
        img_path = os.path.join(args.input_dir, img_name)
        output_path = os.path.join(args.output_dir, f"image_{i:03d}.txt")

        if os.path.isfile(img_path):
            tasks.append((img_path, output_path))
        else:
            print(f"跳过: {img_path} (不存在)")
            # 写入空文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"图片不存在: {img_path}")

    if not tasks:
        print("没有找到任何图片")
        return

    print(f"开始处理 {len(tasks)} 张图片...")

    # 并行处理（最多2张同时）
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(process_and_save, img_path, out_path, args.model, api_key, DEFAULT_PROMPT): img_path
            for img_path, out_path in tasks
        }

        for future in concurrent.futures.as_completed(futures):
            img_path, success, msg = future.result()
            status = "完成" if success else "失败"
            print(f"[{status}] {os.path.basename(img_path)}: {msg}")

    print("全部完成!")

if __name__ == "__main__":
    main()