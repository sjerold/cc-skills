"""
外部 LLM 图片识别脚本（支持批次处理）

通过 API 调用 kimi/qwen 模型识别图片，支持一次处理多张图片

用法:
    python external_ocr.py --images <图片1> <图片2> [--model <模型名>] [--token <API Key>]

参数:
    --images 图片路径（可传多个，最多3张）
    --model  模型名称（默认 kimi-k2-5）
    --token  API Token（或通过环境变量 SP_TOKEN）

返回:
    每张图片的识别结果，格式：
    === <图片名> ===
    [纯文字] 或 [混合] 或 [纯图形]
    OCR 文字内容...
    [需要原图引用]  (混合/纯图形类)
"""

import os
import sys
import base64
import json
import urllib.request
import urllib.error
import concurrent.futures

# 默认提示词模板（内置，无需每次传入）
DEFAULT_PROMPT = """请识别这张图片，并按以下准则处理：

【图片来源】docx 文档中的截图/扫描件
【处理方式】
1. 判断图片类型：
   - 纯文字类：直接OCR识别所有文字，按从上到下、从左到右顺序输出
   - 混合类（文字+流程图）：OCR识别文字，最后输出[需要原图引用]
   - 纯图形类：仅返回[纯图形]

2. 图片分类二次确认：
   - 图形占比>50%才确认为含图形
   - 以文字/表格为主、只有少量装饰图标→归类为纯文字类

3. OCR跳过：页码(1,12,-3-)、版本号(V01xxx)、分隔线(---)、罗马数字(I,II,III)

【输出格式】
第一行：[纯文字] 或 [混合] 或 [纯图形]
第二行起：识别内容（混合类末尾加[需要原图引用])

【禁止】不要编写脚本，不要调用OCR库，只处理这张图片"""


def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_mime_type(image_path):
    ext = os.path.splitext(image_path)[1].lower()
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "image/png")


def call_api(image_base64, mime_type, model, api_key, prompt):
    api_base = "https://coding.dashscope.aliyuncs.com/v1"

    request_body = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        "max_tokens": 4096,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    url = f"{api_base}/chat/completions"
    req = urllib.request.Request(url, data=json.dumps(request_body).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]


def process_image(image_path, model, api_key, prompt):
    """处理单张图片"""
    image_base64 = encode_image(image_path)
    mime_type = get_mime_type(image_path)
    content = call_api(image_base64, mime_type, model, api_key, prompt)
    return image_path, content


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", required=True, help="图片路径（最多3张）")
    parser.add_argument("--model", default="kimi-k2-5", help="模型名称")
    parser.add_argument("--token", default=None, help="API Token")
    parser.add_argument("--prompt", default=None, help="提示词（可选，已内置默认模板）")
    args = parser.parse_args()

    api_key = args.token or os.environ.get("SP_TOKEN")
    if not api_key:
        print("错误: 需要 --token 或 SP_TOKEN 环境变量")
        sys.exit(1)

    # 使用传入的 prompt 或默认模板
    prompt = args.prompt or DEFAULT_PROMPT

    # 验证图片存在
    for img in args.images:
        if not os.path.isfile(img):
            print(f"错误: 图片不存在 {img}")
            sys.exit(1)

    # 并行处理（最多2张同时）
    max_workers = min(2, len(args.images))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_image, img, args.model, api_key, prompt): img
            for img in args.images
        }

        for future in concurrent.futures.as_completed(futures):
            image_path, content = future.result()
            img_name = os.path.basename(image_path)
            print(f"=== {img_name} ===")
            print(content)
            print()


if __name__ == "__main__":
    main()